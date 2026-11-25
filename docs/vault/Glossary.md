---
tags: [icc-bot, glossary]
---

# Glossary

**Alpaca**: US broker with a free paper-trading account and market data API. The bot uses `alpaca-py` 0.45.

**Bracket order**: an entry order with a take-profit and a stop-loss order attached; when one exits, the other is cancelled. Used for stocks only ([[Trade Execution#Stocks: bracket order]]).

**BOS (break of structure)**: a close beyond the last swing high or low. The ICC indication ([[ICC Strategy#The three phases]]).

**Continuation**: the third ICC phase; the close that triggers the entry ([[ICC Strategy]]).

**Correction**: the second ICC phase; the first swing after the break, against the move; it becomes the stop.

**GTC**: good till cancelled.

**HH / HL / LH / LL**: higher high, higher low, lower high, lower low ([[ICC Strategy#Market structure]]).

**ICC**: Indication, Correction, Continuation.

**IEX**: the free single-exchange stock feed the bot reads ([[Market Data#Why the chart may still differ]]).

**Indication**: the first ICC phase; the move that shows direction.

**Paper trading**: simulated trading with fake money on real prices.

**Pivot / swing point**: a bar whose high (or low) is the extreme of the bars around it ([[Signal Engine#Each bar, in the indicator's order]]).

**R**: risk, the distance from entry to stop. TP2 is 2R.

**SIP**: the consolidated US stock feed (all exchanges), which TradingView shows and IEX is not.

**TP1–TP5**: take-profit targets at 1R to 5R; `TARGET_TP_LEVEL` picks the one the bot uses.
