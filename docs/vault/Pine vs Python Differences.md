---
tags: [icc-bot, pine, engine]
---

# Pine vs Python Differences

Since 2026-11-25 the engine follows the [[Pine Script Reference|indicator]] rule for rule ([[Signal Engine]]). With `PIVOT_LEFT = PIVOT_RIGHT = swingLen` the bot should take the trades the chart shows, apart from the differences below.

## What still differs

| Topic | Pine Script | Bot | Effect |
| --- | --- | --- | --- |
| Swing length | One `swingLen` for both sides | `PIVOT_LEFT` and `PIVOT_RIGHT` | Set both to the chart's `swingLen` (default 3) |
| History | The whole chart | The last `LOOKBACK_BARS` (300) | A setup that began before the window is missed |
| Equal highs or lows | Pine's own tie rule | Must be the unique extreme | Rare |
| Data | TradingView's feed | Alpaca crypto, or IEX for stocks | Slightly different candles, see [[Market Data#Why the chart may still differ]] |
| Minimum risk | One tick (`syminfo.mintick`) | `min_tick = 0` | A zero-risk setup is the only one that differs |
| Exits | Draws `EXIT — SL` / `EXIT — TP5` | Exits at `TARGET_TP_LEVEL` (default TP2) or SL, see [[Trade Execution]] | Different on purpose |
| Crypto SELL | Opens a short on the chart | Only closes a long (Alpaca spot can't short) | Different on purpose |

## Before 2026-11-25

The first port used other rules. They are kept here in case old logs are read:

- Indication was a confirmed **HH** pivot (not a close crossing the swing high), and the continuation had to close above that pivot high.
- The correction had to be labelled **HL**.
- A close back through the correction **invalidated** the setup.
- The stop had a 0.1% buffer.
- `PIVOT_RIGHT` defaulted to 1.
