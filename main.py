import os
import re
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("icc-bot")

app = FastAPI(title="ICC Clean Structure Paper Trading Bot")

# Allow your Chrome extension on tradingview.com to send POST requests directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.tradingview.com", "https://tradingview.com"],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "icc_secret_9921")

RISK_PER_TRADE_USD = float(os.getenv("RISK_PER_TRADE_USD", "100.0"))
TARGET_TP_LEVEL = os.getenv("TARGET_TP_LEVEL", "TP2").upper()

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)


def parse_icc_alert(raw_text: str) -> dict:
    """
    Extracts action, ticker, Entry, SL, and TP1-TP5 from the exact Pine Script alert:
    'ICC BUY | AAPL | Entry: 150.00 | SL: 148.00 | TP1: 152.00 | TP2: 154.00 | TP3: 156.00 | TP4: 158.00 | TP5: 160.00'
    """
    match = re.search(
        r"ICC\s+(BUY|SELL)\s*\|\s*([A-Z0-9._/-]+)\s*\|"
        r"\s*Entry:\s*([0-9.]+)\s*\|"
        r"\s*SL:\s*([0-9.]+)\s*\|"
        r"\s*TP1:\s*([0-9.]+)\s*\|"
        r"\s*TP2:\s*([0-9.]+)\s*\|"
        r"\s*TP3:\s*([0-9.]+)\s*\|"
        r"\s*TP4:\s*([0-9.]+)\s*\|"
        r"\s*TP5:\s*([0-9.]+)",
        raw_text,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(f"Could not parse ICC signal from text: {raw_text!r}")

    return {
        "action": match.group(1).upper(),
        "ticker": match.group(2).upper(),
        "levels": {
            "Entry": float(match.group(3)),
            "SL": float(match.group(4)),
            "TP1": float(match.group(5)),
            "TP2": float(match.group(6)),
            "TP3": float(match.group(7)),
            "TP4": float(match.group(8)),
            "TP5": float(match.group(9)),
        },
    }


def normalize_alpaca_symbol(ticker: str) -> tuple[str, bool]:
    """
    Converts TradingView tickers (e.g., BTCUSD, ETHUSDT, AAPL) to Alpaca format.
    Returns (formatted_symbol, is_crypto).
    """
    clean = ticker.replace(".P", "").replace("PERP", "")
    if clean.endswith("USDT"):
        base = clean[:-4]
        return f"{base}/USD", True
    if clean.endswith("USD") and len(clean) > 5 and "/" not in clean:
        base = clean[:-3]
        return f"{base}/USD", True
    if "/" in clean:
        return clean, True
    return clean, False


@app.get("/")
def health_check():
    try:
        account = trading_client.get_account()
        return {
            "status": "online",
            "mode": "PAPER",
            "buying_power": account.buying_power,
            "equity": account.equity,
        }
    except Exception as e:
        return {"status": "online", "alpaca_connection_error": str(e)}


@app.post("/webhook")
async def receive_webhook(request: Request, token: str = ""):
    if token != WEBHOOK_SECRET:
        logger.warning("Blocked unauthorized webhook request.")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    raw_body = (await request.body()).decode("utf-8").strip()
    logger.info(f"Incoming alert payload: {raw_body}")

    try:
        signal = parse_icc_alert(raw_body)
    except ValueError as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e))

    symbol, is_crypto = normalize_alpaca_symbol(signal["ticker"])
    action = signal["action"]
    entry = signal["levels"]["Entry"]
    sl = signal["levels"]["SL"]
    tp = signal["levels"].get(TARGET_TP_LEVEL, signal["levels"]["TP2"])

    stop_distance = abs(entry - sl)
    if stop_distance <= 0:
        raise HTTPException(status_code=400, detail="Stop distance cannot be zero")

    # Position sizing based strictly on the Pine Script's structural SL distance
    qty = round(RISK_PER_TRADE_USD / stop_distance, 4)
    if not is_crypto:
        qty = max(1, int(qty))

    if qty <= 0:
        raise HTTPException(status_code=400, detail="Calculated order quantity is 0")

    side = OrderSide.BUY if action == "BUY" else OrderSide.SELL

    try:
        # Close any open position on this symbol before entering the new direction
        try:
            pos = trading_client.get_open_position(symbol)
            if pos:
                logger.info(f"Closing existing {symbol} position before opening new {action}.")
                trading_client.close_position(symbol)
        except Exception:
            pass

        if is_crypto:
            # Alpaca crypto API executes standard market orders (bracket legs are equities-only on Alpaca)
            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC,
            )
        else:
            # US Stocks/ETFs support full Bracket Orders with SL and TP attached
            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round(tp, 2)),
                stop_loss=StopLossRequest(stop_price=round(sl, 2)),
            )

        order = trading_client.submit_order(order_data=order_req)
        logger.info(
            f"EXECUTED PAPER {action}: {qty} {symbol} | Entry~{entry} | SL={sl} | {TARGET_TP_LEVEL}={tp} | ID={order.id}"
        )
        return {
            "status": "executed",
            "order_id": str(order.id),
            "symbol": symbol,
            "qty": qty,
            "signal": signal,
        }

    except Exception as e:
        logger.error(f"Order execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))