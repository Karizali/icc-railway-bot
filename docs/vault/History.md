---
tags: [icc-bot, history]
---

# History

## `b087b25` "All files completed" (2026-11-15): webhook bot

The first version did no analysis of its own. The [[Pine Script Reference|indicator]] ran on TradingView, and its alerts were POSTed to the bot:

- A **POST webhook** with a shared secret (`WEBHOOK_SECRET`, default `icc_secret_9921`).
- **CORS** open to `tradingview.com`, so a Chrome extension on TradingView could post directly.
- `parse_icc_alert()` read the alert text (`ICC BUY | AAPL | Entry: … | SL: … | TP1: … TP5: …`) with a regex.
- `normalize_alpaca_symbol()` turned TradingView tickers such as `BTCUSD` or `ETHUSDT` into Alpaca's `BTC/USD`.
- Then the same kind of order placement as today.

## `ac64eef` "change in files" (2026-11-15): autonomous scanner

The webhook, CORS, parsing, and symbol mapping were removed, replaced by:

- `icc_engine.py`, a pandas/NumPy port of the indicator ([[Signal Engine]]).
- `fetch_bars()` and a polling loop started from FastAPI's `lifespan` ([[Market Data]], [[Architecture]]).
- `pandas` and `numpy` added to `requirements.txt`.
- `Source Code.txt`, the Pine Script, added for reference.

Left behind: `WEBHOOK_SECRET` in `.env.example`, and the alert's field names (`Entry`, `SL`, `TP1`…) as the signal dict's keys.

Why the switch isn't written down anywhere. The likely reasons are that TradingView webhooks need a paid plan and that the bot can then run without a chart open.

## 2026-11-25: vault, then fixes for deploying

- This vault was added in `docs/vault/`.
- `icc_engine.py` was rewritten to follow the Pine Script rule for rule ([[Pine vs Python Differences]]), with unit tests.
- `main.py`: crypto position symbols fixed, a crypto stop and target added, restart-proof duplicate guard, real-time IEX data with regular hours only, closed candles only, sizing from the latest price, per-symbol error handling, `/health`, an optional `STATUS_TOKEN`, and a startup key check ([[Known Issues#Fixed on 2026-11-25]]).
- `.python-version`, `railway.json`, and a complete `.env.example` added for Railway ([[Deployment]]).
- Every order path was tested with $5 risk on the paper account, then closed out.
