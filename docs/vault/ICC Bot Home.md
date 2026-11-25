---
tags: [icc-bot, moc]
---

# ICC Railway Bot

An autonomous paper-trading bot. Every minute it pulls closed candles from Alpaca, looks for an **ICC** setup (Indication → Correction → Continuation) in the swing structure (HH, HL, LH, LL), and when the latest closed candle completes one, it places a paper order on Alpaca sized to a fixed dollar risk. It runs as a single FastAPI web process on Railway.

The trading logic is a Python port of a TradingView Pine Script indicator, kept in the repo as `Source Code.txt` ([[Pine Script Reference]]).

> [!info] Where things stand (2026-11-26)
> The bot trades **gold only, as GLD** (Alpaca has no spot XAUUSD), on an Alpaca **paper** account (`paper=True` is hardcoded). Its signals were checked alert for alert against `Source Code.txt` and match ([[Pine vs Python Differences]]). It exits at SL or TP5, as the indicator does. A one-year backtest on GLD was about break-even: +$1,169 on $100 risk a trade ([[Backtest]]). 15 tests pass. Open items: [[Known Issues]]. How it got here: [[History]].

## Start here

- [[Getting Started]]: install, configure, and run it locally
- [[Environment Variables]]: every setting and its default
- [[Deployment]]: running it on Railway
- [[Known Issues]]: bugs, risks, and loose ends found while writing this vault
- [[Backtest]]: how to run one, and the results (gold: about break-even; crypto: loses money)

## How it works

- [[Architecture]]: the parts and how one scan flows through them
- [[ICC Strategy]]: the trading idea in plain terms
- [[Signal Engine]]: `icc_engine.py`, pivot detection and the state machine
- [[Market Data]]: `fetch_bars`, crypto against stock data
- [[Trade Execution]]: `execute_paper_trade`, sizing and order types
- [[Status Endpoint]]: the only HTTP route, `GET /`

## Reference

- [[Pine Script Reference]]: the original TradingView indicator
- [[Pine vs Python Differences]]: where the port diverges from it
- [[History]]: from webhook bot to scanner
- [[Glossary]]

## Files in the repo

| File | What it is |
| --- | --- |
| `main.py` | FastAPI app, the scanner loop, data fetching, order placement |
| `icc_engine.py` | `evaluate_icc_structure()`, the signal logic |
| `Source Code.txt` | The Pine Script v6 indicator the engine was ported from |
| `backtest.py` | Replays Alpaca history through the engine ([[Backtest]]) |
| `tests/` | Engine and backtest unit tests ([[Signal Engine#Tests]], [[Backtest#What it simulates]]) |
| `requirements.txt` | Pinned dependencies |
| `.python-version` | `3.13` |
| `Procfile` | `web: uvicorn main:app --host 0.0.0.0 --port $PORT` |
| `railway.json` | Health check and restart policy ([[Deployment#railway.json]]) |
| `.env.example` | Every setting, see [[Environment Variables]] |
| `docs/vault/` | This vault |
