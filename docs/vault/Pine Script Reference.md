---
tags: [icc-bot, pine, reference]
---

# Pine Script Reference

`Source Code.txt` is a TradingView **Pine Script v6** indicator: `ICC Clean Structure — HH HL LH LL` (overlay). It is the original the bot's logic comes from. It does not run in the bot; it's kept for reference and for checking signals on a chart.

## Inputs

| Input | Default | |
| --- | --- | --- |
| Swing Length | 3 | Bars on **each** side of a pivot (`ta.pivothigh(high, 3, 3)`) |
| TP1 … TP5 (R) | 1, 2, 3, 4, 5 | Target multiples of risk |
| Show HH / HL / LH / LL | on | Structure labels |
| Show TP1–TP5 | on | Target lines |
| Keep Only Latest Trade Levels | on | Deletes the previous trade's lines and labels |

## What it does

1. **Swings**: labels each confirmed pivot `HH`/`LH` or `HL`/`LL`; the first of each kind is just `H` or `L`.
2. **Indication** (a break of structure): on a closed bar, `close` crosses above the last swing high → state 1, `indicationHigh = close`. Crossing below the last swing low → state 3, `indicationLow = close`.
3. **Correction**: in state 1, the next pivot low that sits after the last swing high → state 2, `correctionLow` = that low. Mirror for state 3 → 4.
4. **Continuation**: in state 2, a closed bar with `close > indicationHigh` → **BUY**. In state 4, `close < indicationLow` → **SELL**.
5. **Levels**: entry = close, SL = `correctionLow` / `correctionHigh` exactly, TP1–5 = entry ± risk × R. The trade is skipped if risk ≤ one tick.
6. **Drawing**: entry, SL, and TP lines and labels; `EXIT — SL` or `EXIT — TP5` labels when price later touches them.
7. **Alerts**: `alert()` once per bar close, with the text

```
ICC BUY | AAPL | Entry: 150.00 | SL: 148.00 | TP1: 152.00 | TP2: 154.00 | TP3: 156.00 | TP4: 158.00 | TP5: 160.00
```

plus two `alertcondition`s (`ICC BUY Signal`, `ICC SELL Signal`).

That alert text is what the first, webhook version of the bot parsed ([[History]]).

How the Python port differs: [[Pine vs Python Differences]].
