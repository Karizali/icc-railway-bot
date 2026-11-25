---
tags: [icc-bot, strategy]
---

# ICC Strategy

**ICC** stands for **Indication, Correction, Continuation**, a price-structure entry model. The bot trades it on closed candles only, with the same rules as the [[Pine Script Reference|TradingView indicator]].

## Market structure

A **swing high** is a candle whose high is above the highs of the `swingLen` candles on each side; a **swing low** likewise. The indicator labels each one against the previous swing of its kind:

| Label | Meaning |
| --- | --- |
| **HH** | Higher high |
| **LH** | Lower high |
| **HL** | Higher low |
| **LL** | Lower low |

The labels are for reading the chart. The entry rules below only use the swings themselves.

## The three phases

**Bullish (BUY)**

1. **Indication**: a candle **closes above the last swing high** (a break of structure). Its close is the indication level.
2. **Correction**: price pulls back and forms a **swing low** after the broken high. That low is the stop.
3. **Continuation**: a candle **closes above the indication close**. That close is the entry.

**Bearish (SELL)** is the mirror: a close below the last swing low, a swing high after it, then a close below the indication close.

A new break in either direction replaces the setup in progress.

## Trade levels

| Level | Bullish | Bearish |
| --- | --- | --- |
| Entry | Close of the continuation candle | Same |
| Stop loss | The correction swing low | The correction swing high |
| Risk (R) | Entry − SL | SL − Entry |
| TP1…TP5 | Entry + 1R … 5R | Entry − 1R … 5R |

The indicator ends a trade at the SL or at **TP5** (5:1), or replaces it with the next signal. The bot does the same: its target is `TARGET_TP_LEVEL`, default **TP5**. Size is set so a stop-out loses `RISK_PER_TRADE_USD`. See [[Trade Execution]].

The bot trades it on **GLD**, the gold ETF ([[Environment Variables#Gold only (the current setup)]]).

The exact state machine is in [[Signal Engine]].
