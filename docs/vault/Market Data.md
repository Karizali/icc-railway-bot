---
tags: [icc-bot, data]
---

# Market Data

`fetch_bars(symbol)` in `main.py` returns up to `LOOKBACK_BARS` (300) **closed** candles at `TIMEFRAME_MINUTES`, oldest first, or `None` if Alpaca returns nothing.

A symbol containing `/` is **crypto** (`BTC/USD`); anything else is a **US stock or ETF** (`GLD`, the gold ETF the bot trades).

| | Crypto | Stock |
| --- | --- | --- |
| Client | `CryptoHistoricalDataClient()`, no keys | `StockHistoricalDataClient(key, secret)` |
| Feed | Alpaca crypto | `DataFeed.IEX` (free, real time) |
| Window | `TIMEFRAME_MINUTES × 300 × 1.5` minutes back | Enough calendar days for 300 regular-hours bars |
| Hours | 24/7 | **Regular hours only** (9:30–16:00 New York), like a TradingView stock chart |
| When fetched | Every scan | Every scan (a signal after the close waits for the open) |

## Closed candles only

Alpaca returns the candle still forming as the last bar. `fetch_bars` keeps a bar only once `timestamp + TIMEFRAME_MINUTES <= now`, so at 18:20 on 15-minute bars the last bar is the 18:00 one. Checked against live data on 2026-11-25.

## No delay on stocks

The first scanner ended stock requests 16 minutes in the past, assuming the free plan delays data. That limit only applies to the SIP feed: IEX bars and trades arrive in real time on the free plan (checked 2026-11-25), so the delay was removed.

## Latest price

`latest_price(symbol)` reads the latest trade (IEX for stocks). [[Trade Execution]] uses it to size orders and to skip signals the price has already run past, and the crypto take-profit check uses it every scan.

## Why the chart may still differ

- IEX is one exchange, a small share of US volume; TradingView shows consolidated (SIP) data. Stock candles, so swings, can differ a little.
- Crypto candles come from Alpaca's own venues, not the exchange your TradingView chart uses.
