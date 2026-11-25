import os
import math
import time
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    StopLimitOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, OrderStatus, QueryOrderStatus
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    CryptoBarsRequest,
    StockLatestTradeRequest,
    CryptoLatestTradeRequest,
)
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
PIVOT_RIGHT = int(os.getenv("PIVOT_RIGHT", "3"))
LOOKBACK_BARS = int(os.getenv("LOOKBACK_BARS", "300"))
RISK_PER_TRADE_USD = float(os.getenv("RISK_PER_TRADE_USD", "100.0"))
TARGET_TP_LEVEL = os.getenv("TARGET_TP_LEVEL", "TP2").upper()
if TARGET_TP_LEVEL not in {"TP1", "TP2", "TP3", "TP4", "TP5"}:
    TARGET_TP_LEVEL = "TP2"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
STATUS_TOKEN = os.getenv("STATUS_TOKEN", "")

# A crypto stop is a stop-limit: once the stop price trades, sell at no less than this far below it
CRYPTO_STOP_LIMIT_SLIPPAGE = 0.005
# Leave headroom so an order never asks for all of the buying power
BUYING_POWER_USAGE = 0.95
NEW_YORK = ZoneInfo("America/New_York")

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
stock_data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
crypto_data_client = CryptoHistoricalDataClient()  # Crypto data requires no auth keys

# Skip re-evaluating a candle that already produced a trade. After a restart this is empty,
# and the entry order's client_order_id (one per symbol and candle) stops a repeat.
last_traded_bar: dict[str, str] = {}
bot_status = {"last_scan": None, "signals_triggered": 0, "last_signal": None, "last_error": None}
scanner_task: asyncio.Task | None = None
_assets: dict = {}
_clock = {"checked": 0.0, "is_open": False}


def is_crypto(symbol: str) -> bool:
    return "/" in symbol


def position_symbol(symbol: str) -> str:
    # Alpaca's position endpoints want BTCUSD, not BTC/USD
    return symbol.replace("/", "")


def is_not_found(e: Exception) -> bool:
    return isinstance(e, APIError) and e.status_code == 404


def get_asset(symbol: str):
    if symbol not in _assets:
        _assets[symbol] = trading_client.get_asset(position_symbol(symbol))
    return _assets[symbol]


def market_is_open() -> bool:
    if time.monotonic() - _clock["checked"] > 60:
        _clock["is_open"] = trading_client.get_clock().is_open
        _clock["checked"] = time.monotonic()
    return _clock["is_open"]


def round_price(symbol: str, price: float) -> float:
    if is_crypto(symbol):
        increment = get_asset(symbol).price_increment or 0.01
        return round(round(price / increment) * increment, 9)
    return round(price, 2 if price >= 1 else 4)


def floor_qty(qty: float, increment: float) -> float:
    return round(math.floor(qty / increment) * increment, 9)


def latest_price(symbol: str) -> float:
    if is_crypto(symbol):
        trade = crypto_data_client.get_crypto_latest_trade(CryptoLatestTradeRequest(symbol_or_symbols=symbol))
    else:
        trade = stock_data_client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
        )
    return float(trade[symbol].price)


def get_position(symbol: str):
    try:
        return trading_client.get_open_position(position_symbol(symbol))
    except APIError as e:
        if is_not_found(e):
            return None
        raise


def open_orders(symbol: str) -> list:
    orders = trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))
    return [o for o in orders if position_symbol(o.symbol) == position_symbol(symbol)]


def flatten(symbol: str, timeout: float = 30.0) -> None:
    """Cancel the symbol's open orders (bracket legs, crypto stops), close its position, and wait until it is gone."""
    for order in open_orders(symbol):
        trading_client.cancel_order_by_id(order.id)
    if get_position(symbol) is None:
        return
    deadline = time.monotonic() + timeout
    while True:
        try:
            trading_client.close_position(position_symbol(symbol))
            break
        except APIError as e:
            if is_not_found(e):
                return
            # Cancelled orders can take a moment to release the shares they held
            if time.monotonic() > deadline:
                raise
            time.sleep(1)
    while get_position(symbol) is not None:
        if time.monotonic() > deadline:
            raise RuntimeError(f"{symbol} position still open {timeout:.0f}s after closing it")
        time.sleep(1)


def wait_for_fill(order_id, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while True:
        order = trading_client.get_order_by_id(order_id)
        if order.status == OrderStatus.FILLED:
            return order
        if order.status in (OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED):
            raise RuntimeError(f"order {order_id} ended as {order.status.value}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"order {order_id} not filled after {timeout:.0f}s (status {order.status.value})")
        time.sleep(1)


def order_exists(client_order_id: str) -> bool:
    try:
        trading_client.get_order_by_client_id(client_order_id)
        return True
    except APIError as e:
        if is_not_found(e):
            return False
        raise


def fetch_bars(symbol: str) -> pd.DataFrame | None:
    tf = TimeFrame(TIMEFRAME_MINUTES, TimeFrameUnit.Minute)
    now = datetime.now(timezone.utc)

    if is_crypto(symbol):
        # Bars are only produced for minutes with trades, so ask for a little more than needed
        start = now - timedelta(minutes=TIMEFRAME_MINUTES * LOOKBACK_BARS * 1.5)
        req = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=tf, start=start)
        bars = crypto_data_client.get_crypto_bars(req).df
    else:
        # 6.5 regular-hours trading hours a day, 5 trading days a week, plus holidays
        days = math.ceil(TIMEFRAME_MINUTES * LOOKBACK_BARS / 390 * 7 / 5) + 4
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=now - timedelta(days=days),
            feed=DataFeed.IEX,
        )
        bars = stock_data_client.get_stock_bars(req).df

    if bars.empty:
        return None

    df = bars.reset_index()
    if not is_crypto(symbol):
        # Regular trading hours only, like a TradingView stock chart
        local = df["timestamp"].dt.tz_convert(NEW_YORK)
        minutes = local.dt.hour * 60 + local.dt.minute
        df = df[(minutes >= 9 * 60 + 30) & (minutes < 16 * 60)]
    # Keep closed candles only: a bar is closed once its whole timeframe has passed
    df = df[df["timestamp"] + pd.Timedelta(minutes=TIMEFRAME_MINUTES) <= pd.Timestamp(now)]
    return df.tail(LOOKBACK_BARS).reset_index(drop=True)


def crypto_stop_client_id(symbol: str, bar_epoch: int, tp: float) -> str:
    # The target is kept in the stop order's id, so it survives restarts with no database
    return f"icc-sl-{position_symbol(symbol)}-{bar_epoch}-tp{tp}"


def target_from_stop(order) -> float | None:
    coid = order.client_order_id or ""
    if not coid.startswith("icc-sl-") or "-tp" not in coid:
        return None
    try:
        return float(coid.rsplit("-tp", 1)[1])
    except ValueError:
        return None


def manage_crypto_exit(symbol: str) -> None:
    """Crypto has no bracket orders: the stop rests on Alpaca, and the bot takes profit when the target trades."""
    stops = [o for o in open_orders(symbol) if (o.client_order_id or "").startswith("icc-sl-")]
    if not stops:
        return
    position = get_position(symbol)
    if position is None:
        for order in stops:
            trading_client.cancel_order_by_id(order.id)
        logger.info(f"{symbol}: no position left, cancelled {len(stops)} leftover stop order(s).")
        return
    target = target_from_stop(stops[0])
    if target is None:
        return
    price = latest_price(symbol)
    if price >= target:
        flatten(symbol)
        logger.info(f"TAKE PROFIT {symbol} at ~{price} (target {target}).")


def execute_paper_trade(symbol: str, signal: dict) -> None:
    action = signal["action"]
    sl = signal["SL"]
    tp = signal[TARGET_TP_LEVEL]
    bar_epoch = int(pd.Timestamp(signal["timestamp"]).timestamp())
    client_order_id = f"icc-{position_symbol(symbol)}-{action}-{bar_epoch}"

    if order_exists(client_order_id):
        logger.info(f"{symbol}: {action} for candle {signal['timestamp']} was already placed, skipping.")
        return

    if is_crypto(symbol):
        if action == "SELL":
            # Alpaca spot crypto cannot be shorted: a SELL only closes a long
            if get_position(symbol) is not None:
                flatten(symbol)
                logger.info(f"Closed long {symbol} on ICC SELL signal.")
            else:
                logger.info(f"Skipping {symbol} SELL signal (no long position to close).")
            return
    elif not market_is_open():
        logger.info(f"Skipping {symbol} {action} signal: market is closed.")
        return

    price = latest_price(symbol)
    long = action == "BUY"
    if (long and not sl < price < tp) or (not long and not tp < price < sl):
        logger.info(f"Skipping {symbol} {action}: price {price} is already outside SL {sl} / {TARGET_TP_LEVEL} {tp}.")
        return

    asset = get_asset(symbol)
    if not long and not asset.shortable:
        logger.info(f"Skipping {symbol} SELL: not shortable on Alpaca.")
        return

    # Size so that a stop-out loses RISK_PER_TRADE_USD, measured from the price we will actually get
    qty = RISK_PER_TRADE_USD / abs(price - sl)
    account = trading_client.get_account()
    buying_power = float(account.non_marginable_buying_power if is_crypto(symbol) else account.buying_power)
    max_qty = buying_power * BUYING_POWER_USAGE / price
    if qty > max_qty:
        logger.info(f"{symbol}: size capped by buying power ({qty:.6f} -> {max_qty:.6f}).")
        qty = max_qty

    if is_crypto(symbol):
        qty = floor_qty(qty, asset.min_trade_increment or 1e-9)
        if qty < (asset.min_order_size or 0) or qty <= 0:
            logger.info(f"Skipping {symbol} BUY: size {qty} is below Alpaca's minimum.")
            return
    else:
        qty = int(qty)
        if qty < 1:
            logger.info(f"Skipping {symbol} {action}: one share would risk more than ${RISK_PER_TRADE_USD}.")
            return

    flatten(symbol)

    if is_crypto(symbol):
        order = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                client_order_id=client_order_id,
            )
        )
        try:
            wait_for_fill(order.id)
            # Fees come out of the coin received, so protect what is actually held
            held = floor_qty(float(get_position(symbol).qty_available), asset.min_trade_increment or 1e-9)
            stop_price = round_price(symbol, sl)
            trading_client.submit_order(
                StopLimitOrderRequest(
                    symbol=symbol,
                    qty=held,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    stop_price=stop_price,
                    limit_price=round_price(symbol, sl * (1 - CRYPTO_STOP_LIMIT_SLIPPAGE)),
                    client_order_id=crypto_stop_client_id(symbol, bar_epoch, round_price(symbol, tp)),
                )
            )
        except Exception:
            logger.exception(f"Could not protect the new {symbol} position with a stop; closing it.")
            flatten(symbol)
            raise
    else:
        order = trading_client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if long else OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round_price(symbol, tp)),
                stop_loss=StopLossRequest(stop_price=round_price(symbol, sl)),
                client_order_id=client_order_id,
            )
        )

    bot_status["signals_triggered"] += 1
    bot_status["last_signal"] = {"symbol": symbol, **signal, "qty": qty, "order_id": str(order.id)}
    logger.info(
        f"EXECUTED {action} {qty} {symbol} | ~{price} (signal {signal['Entry']}) | SL={sl} | {TARGET_TP_LEVEL}={tp} | ID={order.id}"
    )


def scan_symbol(symbol: str) -> None:
    if is_crypto(symbol):
        manage_crypto_exit(symbol)
    elif not market_is_open():
        return

    df = fetch_bars(symbol)
    if df is None or df.empty:
        return

    signal = evaluate_icc_structure(df, left=PIVOT_LEFT, right=PIVOT_RIGHT)
    if signal and last_traded_bar.get(symbol) != signal["timestamp"]:
        last_traded_bar[symbol] = signal["timestamp"]
        logger.info(f"ICC Signal Detected on {symbol}: {signal}")
        execute_paper_trade(symbol, signal)


async def market_scanner_loop():
    logger.info(f"Starting 24/7 ICC Scanner for {SYMBOLS} on {TIMEFRAME_MINUTES}m timeframe...")
    while True:
        bot_status["last_scan"] = datetime.now(timezone.utc).isoformat()
        for symbol in SYMBOLS:
            try:
                await asyncio.to_thread(scan_symbol, symbol)
            except Exception as e:
                bot_status["last_error"] = f"{datetime.now(timezone.utc).isoformat()} {symbol}: {e}"
                logger.exception(f"Scan failed for {symbol}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scanner_task
    # Fail the deploy loudly if the keys are wrong, instead of scanning with nothing able to trade
    account = await asyncio.to_thread(trading_client.get_account)
    logger.info(f"Connected to Alpaca paper account {account.account_number} (equity {account.equity}).")
    scanner_task = asyncio.create_task(market_scanner_loop())
    yield
    scanner_task.cancel()


app = FastAPI(title="Autonomous ICC Structure Bot", lifespan=lifespan)


def scanner_running() -> bool:
    return scanner_task is not None and not scanner_task.done()


@app.get("/health")
def health(response: Response):
    if not scanner_running():
        response.status_code = 503
    return {"scanner_running": scanner_running(), "last_scan": bot_status["last_scan"]}


@app.get("/")
def status(token: str = ""):
    if STATUS_TOKEN and token != STATUS_TOKEN:
        raise HTTPException(status_code=401, detail="Add ?token=<STATUS_TOKEN> to the URL.")
    result = {
        "status": "running_24_7" if scanner_running() else "scanner_stopped",
        "mode": "ALPACA_PAPER",
        "symbols": SYMBOLS,
        "timeframe_minutes": TIMEFRAME_MINUTES,
        **bot_status,
    }
    try:
        account = trading_client.get_account()
        result["equity"] = account.equity
        result["buying_power"] = account.buying_power
        result["positions"] = [
            {"symbol": p.symbol, "side": p.side.value, "qty": p.qty, "unrealized_pl": p.unrealized_pl}
            for p in trading_client.get_all_positions()
        ]
    except Exception as e:
        result["account_error"] = str(e)
    return result
