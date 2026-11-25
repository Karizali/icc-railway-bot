---
tags: [icc-bot, pine, engine]
---

# Pine vs Python Differences

**The strategy logic matches `Source Code.txt`.** On 2026-11-26 the engine was checked against a separate, literal transliteration of the Pine Script on real GLD and BTC/USD candles, and every alert was identical ([[Signal Engine#Verified against Source Code.txt (2026-11-26)]]). Given the **same candles**, the bot and the indicator fire the same BUY and SELL, with the same entry, SL, and TP1–TP5.

The exit matches too: the indicator ends a trade at its SL or at TP5 (`EXIT — TP5`), and a new signal replaces the trade. The bot exits at SL or `TARGET_TP_LEVEL`, default **TP5**, and a new signal closes the trade and opens the new one.

## What can still differ: the candles

| Topic | Your TradingView chart | The bot | What to do |
| --- | --- | --- | --- |
| Instrument | Often `XAUUSD` (spot gold, almost 24 hours) | **GLD** (SPDR Gold Shares ETF); Alpaca has no spot gold | Put the indicator on **`AMEX:GLD`** to see the bot's signals |
| Hours | Depends on the chart | Regular hours only, 9:30–16:00 New York | Leave TradingView's extended hours **off** |
| Data feed | Consolidated (all US exchanges) | IEX (one exchange, free) | Small differences in highs and lows can move a swing |
| Equal highs or lows | TradingView's own rule | PyneCore's rule (newest wins) | Not confirmed on TradingView itself; matters only on exact ties |
| History | Whole chart | Last 300 candles | Proven not to matter (0 differences in a year of GLD) |

## Where the bot has to act differently

- **Signals after the close.** The 15:45 candle closes at 16:00, when the market is shut. The indicator alerts then; the bot places that trade at the **next open**, after checking that price hasn't already passed the SL or target.
- **Crypto shorts.** Alpaca spot crypto can't be shorted, so a crypto SELL only closes a long. This doesn't apply to GLD, which can be shorted.
- **Fill prices.** The indicator's entry is the candle's close; the bot buys a moment later at market. Size is worked out from the real price so the dollar risk stays the same.

## Before 2026-11-26

- Until 2026-11-25 the engine used different rules: a confirmed HH pivot as the indication, an HL-only correction, invalidation, a 0.1% stop buffer, and `PIVOT_RIGHT=1`.
- From 2026-11-25 to 2026-11-26 it followed the Pine rules, but required a swing to be strictly the highest on both sides, ignored `syminfo.mintick`, and the bot exited at TP2.
