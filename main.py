import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

from icc_engine import evaluate_icc_structure

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("icc-autonomous-bot")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", "BTC/USD,ETH/USD").split(",") if s.strip()]
TIMEFRAME_MINUTES = int(os.getenv("TIMEFRAME_MINUTES", "15"))
PIVOT_LEFT = int(os.getenv("PIVOT_LEFT", "3"))
PIVOT_RIGHT = int(os.getenv("PIVOT_RIGHT", "1"))
RISK_PER_TRADE_USD = float(os.getenv("RISK_PER_TRADE_USD", "100.0"))
TARGET_TP_LEVEL = os.getenv("TARGET_TP_LEVEL", "TP2").upper()
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
stock_data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
crypto_data_client = CryptoHistoricalDataClient()  # Crypto data requires no auth keys

# Prevent duplicate trades on the same candle timestamp
last_traded_bar: dict[str, str] = {}
bot_status = {"last_scan": None, "signals_triggered": 0, "last_signal": None}


def fetch_bars(symbol: str, limit: int = 120):
    is_crypto = "/" in symbol
    tf = TimeFrame(TIMEFRAME_MINUTES, TimeFrameUnit.Minute)

    if is_crypto:
        start_time = datetime.now(timezone.utc) - timedelta(minutes=TIMEFRAME_MINUTES * limit)
        req = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start_time,
        )
        bars = crypto_data_client.get_crypto_bars(req).df
    else:
        # Free Alpaca stock data requires a 15-minute offset on end time
        end_time = datetime.now(timezone.utc) - timedelta(minutes=16)
        start_time = end_time - timedelta(days=5)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start_time,
            end=end_time,
            feed=DataFeed.IEX,
        )
        bars = stock_data_client.get_stock_bars(req).df

    if bars.empty:
        return None

    df = bars.reset_index()
    # Drop the currently forming (unclosed) candle so we only evaluate closed bars
    if len(df) > 1:
        df = df.iloc[:-1].copy()
    return df


def execute_paper_trade(symbol: str, signal: dict):
    is_crypto = "/" in symbol
    action = signal["action"]
    entry = signal["Entry"]
    sl = signal["SL"]
    tp = signal.get(TARGET_TP_LEVEL, signal["TP2"])

    stop_distance = abs(entry - sl)
    if stop_distance <= 0:
        return

    qty = round(RISK_PER_TRADE_USD / stop_distance, 4)
    if not is_crypto:
        qty = max(1, int(qty))

    if qty <= 0:
        return

    side = OrderSide.BUY if action == "BUY" else OrderSide.SELL

    # Alpaca crypto does not allow shorting in standard spot paper accounts
    if is_crypto and action == "SELL":
        try:
            pos = trading_client.get_open_position(symbol)
            if pos:
                logger.info(f"Closing long {symbol} position on ICC SELL signal.")
                trading_client.close_position(symbol)
        except Exception:
            logger.info(f"Skipping {symbol} SELL signal (no open long spot position to close).")
        return

    try:
        # Close existing opposite position if open
        try:
            pos = trading_client.get_open_position(symbol)
            if pos:
                trading_client.close_position(symbol)
        except Exception:
            pass

        if is_crypto:
            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC,
            )
        else:
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
        bot_status["signals_triggered"] += 1
        bot_status["last_signal"] = {"symbol": symbol, **signal, "order_id": str(order.id)}
        logger.info(
            f"EXECUTED {action} {qty} {symbol} | Entry~{entry} | SL={sl} | {TARGET_TP_LEVEL}={tp} | ID={order.id}"
        )
    except Exception as e:
        logger.error(f"Failed to submit order for {symbol}: {e}")


async def market_scanner_loop():
    logger.info(f"Starting 24/7 ICC Scanner for {SYMBOLS} on {TIMEFRAME_MINUTES}m timeframe...")
    while True:
        try:
            bot_status["last_scan"] = datetime.now(timezone.utc).isoformat()
            for symbol in SYMBOLS:
                df = await asyncio.to_thread(fetch_bars, symbol)
                if df is None or df.empty:
                    continue

                signal = evaluate_icc_structure(df, left=PIVOT_LEFT, right=PIVOT_RIGHT)
                if signal:
                    bar_ts = signal["timestamp"]
                    if last_traded_bar.get(symbol) != bar_ts:
                        last_traded_bar[symbol] = bar_ts
                        logger.info(f"ICC Signal Detected on {symbol}: {signal}")
                        await asyncio.to_thread(execute_paper_trade, symbol, signal)
        except Exception as e:
            logger.error(f"Scanner loop error: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(market_scanner_loop())
    yield
    task.cancel()


app = FastAPI(title="Autonomous ICC Structure Bot", lifespan=lifespan)


@app.get("/")
def status():
    account = trading_client.get_account()
    return {
        "status": "running_24_7",
        "mode": "ALPACA_PAPER",
        "symbols": SYMBOLS,
        "timeframe_minutes": TIMEFRAME_MINUTES,
        "equity": account.equity,
        "buying_power": account.buying_power,
        **bot_status,
    }