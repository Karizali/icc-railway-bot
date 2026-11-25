---
tags: [icc-bot, moc]
---

# ICC Railway Bot

An autonomous paper-trading bot. Every minute it pulls closed candles from Alpaca, looks for an **ICC** setup (Indication → Correction → Continuation) in the swing structure (HH, HL, LH, LL), and when the latest closed candle completes one, it places a paper order on Alpaca sized to a fixed dollar risk. It runs as a single FastAPI web process on Railway.

The trading logic is a Python port of a TradingView Pine Script indicator, kept in the repo as `Source Code.txt` ([[Pine Script Reference]]).

> [!info] Where things stand (2026-11-25)
> The bot runs and is ready for Railway. On 2026-11-25 the engine was rewritten to follow the Pine Script rule for rule, and the execution layer was fixed: crypto positions get a real stop and target, restarts can't repeat a trade, stock data is real time, and every order path was tested on the paper account. 7 engine tests pass. Paper trading only (`paper=True` is hardcoded). What was fixed and what is still open: [[Known Issues]]. How it got here: [[History]].

## Start here

- [[Getting Started]]: install, configure, and run it locally
- [[Environment Variables]]: every setting and its default
- [[Deployment]]: running it on Railway
- [[Known Issues]]: bugs, risks, and loose ends found while writing this vault

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
| `tests/test_icc_engine.py` | Engine unit tests ([[Signal Engine#Tests]]) |
| `requirements.txt` | Pinned dependencies |
| `.python-version` | `3.13` |
| `Procfile` | `web: uvicorn main:app --host 0.0.0.0 --port $PORT` |
| `railway.json` | Health check and restart policy ([[Deployment#railway.json]]) |
| `.env.example` | Every setting, see [[Environment Variables]] |
| `docs/vault/` | This vault |
