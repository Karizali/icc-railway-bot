---
tags: [icc-bot, config]
---

# Environment Variables

Read once at import time in `main.py` (from `.env` locally, from the service's Variables on Railway). Changing one needs a restart. `.env.example` lists all of them.

| Variable | Default | Used for |
| --- | --- | --- |
| `ALPACA_API_KEY` | `""` | Trading and stock data. **Required**: startup fails without valid keys |
| `ALPACA_SECRET_KEY` | `""` | Same |
| `SYMBOLS` | `BTC/USD,ETH/USD` | Comma-separated. A `/` marks crypto, anything else is a US stock ([[Market Data]]) |
| `TIMEFRAME_MINUTES` | `15` | Candle size, 1 to 59 |
| `PIVOT_LEFT` | `3` | Bars left of a swing point |
| `PIVOT_RIGHT` | `3` | Bars right of it, which is also how many bars a swing takes to confirm |
| `LOOKBACK_BARS` | `300` | Candles fed to the engine each scan |
| `RISK_PER_TRADE_USD` | `100.0` | Dollars lost if the stop is hit ([[Trade Execution#Position size]]) |
| `TARGET_TP_LEVEL` | `TP2` | `TP1` to `TP5`; anything else means `TP2` |
| `POLL_INTERVAL_SECONDS` | `60` | Pause between scans |
| `STATUS_TOKEN` | `""` | If set, the [[Status Endpoint]] needs `?token=<value>` |

> [!important] Match the chart
> Set `PIVOT_LEFT` and `PIVOT_RIGHT` both to the indicator's **Swing Length** (3 unless you changed it on TradingView). Different values give different swings, so different signals. See [[Pine vs Python Differences]].

`WEBHOOK_SECRET` from the webhook version ([[History]]) is no longer used.

## Examples

Stocks and crypto together, 5-minute candles:

```env
SYMBOLS=AAPL,TSLA,BTC/USD
TIMEFRAME_MINUTES=5
```
