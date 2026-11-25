---
tags: [icc-bot, issues]
---

# Known Issues

The first list was found by reading the code on 2026-11-25; the fixes landed the same day.

## Fixed on 2026-11-25

- [x] **Crypto positions couldn't be found or closed.** Alpaca's position endpoint needs `BTCUSD`; the code passed `BTC/USD` and got "Not Found", so a SELL never closed a crypto long. Fixed with `position_symbol()`.
- [x] **Crypto trades had no stop or target.** Now a stop-limit rests on Alpaca and the bot takes profit at the target ([[Trade Execution#Crypto: stop on Alpaca, target watched by the bot]]).
- [x] **The engine didn't follow the Pine Script.** Rewritten to match it ([[Pine vs Python Differences]]).
- [x] **Duplicate trades after a restart.** The entry's `client_order_id` is now unique per candle and checked first.
- [x] **Old bracket legs survived a reversal.** `flatten()` cancels the symbol's orders before closing.
- [x] **Stock data was 16 minutes delayed** for no reason (IEX is real time on the free plan).
- [x] **The forming candle was handled by luck.** Bars are now kept only once closed.
- [x] **Stock signals included extended hours.** Now regular hours only.
- [x] **Size used the stale signal price.** Now the latest trade, capped by buying power; under 1 share is skipped.
- [x] **Signals already run past SL or target were traded.** Now skipped.
- [x] **One symbol's error skipped the rest of the scan.** Now each symbol has its own `try`.
- [x] **`GET /` returned 500 when Alpaca failed**, and said `running_24_7` even with the scanner dead. Fixed; `/health` added.
- [x] **Bad keys were found only at the first trade.** Startup now fails.
- [x] **No tests.** `tests/test_icc_engine.py`.
- [x] **`.env.example` was incomplete**, and there was no Python pin. Fixed; `.python-version` and `railway.json` added.

## Still open

- [ ] **The crypto target only works while the bot runs.** The stop is on Alpaca; the take-profit check is the bot's. If the bot is down when price hits the target, the position stays open, still protected by the stop.
- [ ] **The crypto stop is a stop-limit** with a 0.5% limit. In a gap through that range it may not fill. Alpaca has no plain stop orders for crypto.
- [ ] **Memory is ~118 MB**, just over what Railway's Free plan pays for, so it stops for a few days a month on that plan ([[Deployment#Free plan]]). Dropping `alpaca-py` and pandas for plain HTTP calls would roughly halve it.
- [ ] **Short stock positions** hold a bracket like longs, but borrow fees and hard-to-borrow recalls aren't handled.
- [ ] **On gold the strategy is only about break-even**: +$1,169 in a year on $100 risk a trade, with a $4,359 worst losing run. On crypto it lost heavily, mostly to fees. See [[Backtest]].
- [ ] **Equal highs and lows** follow PyneCore's tie rule (newest wins), which hasn't been confirmed on TradingView itself. It only matters on exact ties.
- [ ] **GLD is not XAUUSD.** The bot's signals match the indicator on an `AMEX:GLD` chart (regular hours), not on a spot-gold chart. See [[Pine vs Python Differences#What can still differ: the candles]].
- [ ] `Source Code.txt` would be easier to find as `icc_indicator.pine`.
