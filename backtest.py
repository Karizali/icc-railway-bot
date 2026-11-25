"""
Backtest the ICC bot on Alpaca history.

Runs the engine over the whole history in one pass, as TradingView runs the indicator over a
chart. (The live bot's 300-candle window gives the same signals: checked on a year of GLD.)
Then simulates the live bot's orders:

- A signal is known when its candle closes; the bot acts at the next candle's open.
  For a stock, a signal on the day's last candle is acted on at the next day's open.
- Skipped like live: price already past SL or target, size under 1 share, crypto SELL with no long.
- A new signal closes the open position first (live `flatten`), then enters.
- Stocks: bracket exit at SL or target. Crypto: stop at SL, target taken by the bot,
  and a crypto SELL signal closes the long.
- If a candle touches both SL and target, the stop is assumed to come first (the cautious choice).
- A candle that opens past a level fills at the open.

Usage:
    python backtest.py --days 180
    python backtest.py --days 90 --symbols BTC/USD,AAPL --right 3 --csv trades.csv
"""
import argparse
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone

import pandas as pd

from icc_engine import icc_signals

STARTING_EQUITY = 100_000.0


@dataclass
class Config:
    left: int = 3
    right: int = 3
    lookback: int = 300
    risk_usd: float = 100.0
    target: str = "TP5"
    timeframe_minutes: int = 15
    min_tick: float = 0.01  # syminfo.mintick
    crypto_fee: float = 0.0025  # Alpaca's lowest-volume crypto taker fee, per side
    slippage: float = 0.0002  # per side, on market fills and stops
    equity: float = STARTING_EQUITY
    hold: bool = False  # True: ignore new signals while a trade is open (the live bot closes and re-enters)


@dataclass
class Trade:
    symbol: str
    side: str
    entry_time: str
    entry: float
    sl: float
    tp: float
    qty: float
    exit_time: str = ""
    exit: float = 0.0
    reason: str = ""
    pnl: float = 0.0
    r: float = 0.0


def simulate(symbol: str, df: pd.DataFrame, cfg: Config) -> list[Trade]:
    crypto = "/" in symbol
    signals = {s["bar"]: s for s in icc_signals(df, cfg.left, cfg.right, cfg.min_tick)}
    fee = cfg.crypto_fee if crypto else 0.0
    trades: list[Trade] = []
    position: Trade | None = None
    pending: dict | None = None

    opens = df["open"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    closes = df["close"].astype(float).tolist()
    times = df["timestamp"].tolist()

    def close_position(i: int, price: float, reason: str, slip: bool = True) -> None:
        nonlocal position
        long = position.side == "BUY"
        if slip:
            price *= (1 - cfg.slippage) if long else (1 + cfg.slippage)
        gross = (price - position.entry) * position.qty * (1 if long else -1)
        fees = (position.entry + price) * position.qty * fee
        position.exit_time = str(times[i])
        position.exit = round(price, 6)
        position.reason = reason
        position.pnl = round(gross - fees, 2)
        position.r = round(position.pnl / cfg.risk_usd, 2)
        trades.append(position)
        position = None

    for i in range(cfg.lookback - 1, len(df)):
        # 1. Act on the previous candle's signal at this candle's open
        if pending is not None:
            signal, pending = pending, None
            long = signal["action"] == "BUY"
            if position is not None:
                close_position(i, opens[i], "new signal")
            if long or not crypto:
                price = opens[i] * ((1 + cfg.slippage) if long else (1 - cfg.slippage))
                sl, tp = signal["SL"], signal[cfg.target]
                if (long and sl < price < tp) or (not long and tp < price < sl):
                    qty = cfg.risk_usd / abs(price - sl)
                    cap = cfg.equity * (0.95 if crypto else 1.9) / price
                    qty = min(qty, cap)
                    qty = math.floor(qty * 1e6) / 1e6 if crypto else int(qty)
                    if qty > 0:
                        position = Trade(symbol, signal["action"], str(times[i]), round(price, 6), sl, tp, qty)

        # 2. Exits inside this candle
        if position is not None:
            long = position.side == "BUY"
            sl, tp = position.sl, position.tp
            if long and lows[i] <= sl:
                close_position(i, min(opens[i], sl), "stop loss")
            elif not long and highs[i] >= sl:
                close_position(i, max(opens[i], sl), "stop loss")
            elif long and highs[i] >= tp:
                # Stock target is a resting limit (fills at TP or a better open); crypto is a market sell at TP
                close_position(i, max(opens[i], tp), "target", slip=crypto)
            elif not long and lows[i] <= tp:
                close_position(i, min(opens[i], tp), "target", slip=crypto)

        # 3. The signal this candle's close produces
        signal = signals.get(i)
        if signal is None or i + 1 >= len(df) or (cfg.hold and position is not None):
            continue
        pending = signal

    if position is not None:
        close_position(len(df) - 1, closes[-1], "still open")
    return trades


def max_drawdown(pnls: list[float], equity: float) -> float:
    peak = curve = equity
    worst = 0.0
    for p in pnls:
        curve += p
        peak = max(peak, curve)
        worst = min(worst, curve - peak)
    return worst


def summarize(name: str, trades: list[Trade], cfg: Config) -> dict:
    closed = [t for t in trades if t.reason != "still open"]
    wins = [t for t in closed if t.pnl > 0]
    gains = sum(t.pnl for t in wins)
    losses = -sum(t.pnl for t in closed if t.pnl <= 0)
    return {
        "symbol": name,
        "trades": len(closed),
        "win %": round(100 * len(wins) / len(closed), 1) if closed else 0.0,
        "net P&L $": round(sum(t.pnl for t in trades), 2),
        "avg R": round(sum(t.r for t in closed) / len(closed), 2) if closed else 0.0,
        "profit factor": round(gains / losses, 2) if losses else float("inf") if gains else 0.0,
        "max drawdown $": round(max_drawdown([t.pnl for t in sorted(trades, key=lambda t: t.exit_time)], cfg.equity), 2),
        "targets": sum(t.reason == "target" for t in closed),
        "stops": sum(t.reason == "stop loss" for t in closed),
        "closed by signal": sum(t.reason == "new signal" for t in closed),
    }


def main() -> None:
    import main as bot  # Alpaca clients and settings from .env

    p = argparse.ArgumentParser(description="Backtest the ICC bot on Alpaca history.")
    p.add_argument("--days", type=int, default=180, help="how far back to test (default 180)")
    p.add_argument("--symbols", default=",".join(bot.SYMBOLS), help="comma-separated, default SYMBOLS from .env")
    p.add_argument("--timeframe", type=int, default=bot.TIMEFRAME_MINUTES, help="candle minutes")
    p.add_argument("--left", type=int, default=bot.PIVOT_LEFT)
    p.add_argument("--right", type=int, default=bot.PIVOT_RIGHT)
    p.add_argument("--risk", type=float, default=bot.RISK_PER_TRADE_USD, help="dollars risked per trade")
    p.add_argument("--target", default=bot.TARGET_TP_LEVEL, choices=["TP1", "TP2", "TP3", "TP4", "TP5"])
    p.add_argument("--crypto-fee", type=float, default=0.0025, help="per side, default 0.0025 (0.25%%)")
    p.add_argument("--slippage", type=float, default=0.0002, help="per side, default 0.0002 (0.02%%)")
    p.add_argument("--hold", action="store_true", help="ignore new signals while a trade is open")
    p.add_argument("--csv", help="write every trade to this CSV file")
    args = p.parse_args()

    cfg = Config(
        left=args.left,
        right=args.right,
        lookback=bot.LOOKBACK_BARS,
        risk_usd=args.risk,
        target=args.target,
        timeframe_minutes=args.timeframe,
        crypto_fee=args.crypto_fee,
        slippage=args.slippage,
        hold=args.hold,
    )
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    end = datetime.now(timezone.utc)
    test_start = end - timedelta(days=args.days)

    print(
        f"ICC backtest: {args.days} days to {end:%Y-%m-%d}, {cfg.timeframe_minutes}m candles, "
        f"pivots {cfg.left}/{cfg.right}, ${cfg.risk_usd:g} risk, {cfg.target}, "
        f"crypto fee {cfg.crypto_fee:.2%}/side, slippage {cfg.slippage:.2%}/side"
        f"{', holding through new signals' if cfg.hold else ''}\n"
    )
    all_trades: list[Trade] = []
    rows = []
    for symbol in symbols:
        # Warm-up: enough history before the test start to fill the first window
        warmup_days = math.ceil(cfg.lookback * cfg.timeframe_minutes / (1440 if "/" in symbol else 390) * 1.6) + 4
        df = bot.get_bars(symbol, test_start - timedelta(days=warmup_days), timeframe_minutes=cfg.timeframe_minutes)
        before = (df["timestamp"] < pd.Timestamp(test_start)).sum()
        if before < cfg.lookback - 1:
            print(f"{symbol}: not enough history, skipped")
            continue
        df = df.iloc[before - (cfg.lookback - 1) :].reset_index(drop=True)
        print(f"{symbol}: {len(df) - cfg.lookback + 1} candles, {df['timestamp'].iloc[cfg.lookback - 1]:%Y-%m-%d} to {df['timestamp'].iloc[-1]:%Y-%m-%d}...", flush=True)
        trades = simulate(symbol, df, Config(**{**cfg.__dict__, "min_tick": bot.tick_size(symbol)}))
        all_trades += trades
        row = summarize(symbol, trades, cfg)
        first, last = float(df["open"].iloc[cfg.lookback - 1]), float(df["close"].iloc[-1])
        row["price change %"] = round(100 * (last / first - 1), 1)
        rows.append(row)

    if not rows:
        return
    total = summarize("TOTAL", all_trades, cfg)
    total["price change %"] = ""
    rows.append(total)
    print()
    print(pd.DataFrame(rows).set_index("symbol").to_string())
    print(
        f"\nWin % needed to break even at {cfg.target} before costs: {100 / (1 + int(cfg.target[2:])):.0f}%. "
        f"Max drawdown is the deepest fall from a peak in the closed-trade P&L."
    )
    if args.csv:
        pd.DataFrame([asdict(t) for t in sorted(all_trades, key=lambda t: t.entry_time)]).to_csv(args.csv, index=False)
        print(f"Trades written to {args.csv}")


if __name__ == "__main__":
    main()
