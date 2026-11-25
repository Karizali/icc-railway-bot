---
tags: [icc-bot, backtest]
---

# Backtest

`backtest.py` runs the engine (`icc_signals`) over Alpaca history in one pass, as TradingView runs the indicator over a chart, and simulates the live bot's orders ([[Trade Execution]]). That gives the same signals as the bot's 300-candle window ([[Signal Engine#Verified against Source Code.txt (2026-11-26)]]) and is much faster.

```bash
python backtest.py --days 180                       # SYMBOLS and settings from .env
python backtest.py --days 90 --symbols BTC/USD,AAPL --right 3 --target TP3 --csv trades.csv
python backtest.py --days 180 --crypto-fee 0 --slippage 0   # the strategy before costs
python backtest.py --days 180 --hold                 # ignore new signals while a trade is open
```

Options: `--days`, `--symbols`, `--timeframe` (1–59), `--left`, `--right`, `--risk`, `--target`, `--crypto-fee` (per side, default 0.25%), `--slippage` (per side, default 0.02%), `--hold`, `--csv`. Run one at a time: several in parallel can hit Alpaca's 200 requests a minute.

## What it simulates

- A signal is known when its candle closes, and the trade is entered at the **next candle's open**. For a stock or ETF, a signal on the day's last candle is entered at the next day's open, as the live bot does.
- The same skips as live: price already past SL or target, less than 1 share, a crypto SELL with no long.
- `syminfo.mintick` is the symbol's tick ($0.01 for GLD), and the default target is **TP5**.
- Size: `$risk / |entry − SL|`, capped at 95% of $100,000 for crypto and 190% for stocks.
- Exits: SL or target inside a candle. A candle that opens past a level fills at the open. **If one candle touches both, the stop counts first** (the cautious choice).
- A new signal closes the open trade at the next open, then enters (as the live bot's `flatten` does), unless `--hold` is set.
- Costs: crypto 0.25% a side (Alpaca's lowest-volume taker fee); stocks have no commission. 0.02% slippage a side on market fills and stops.
- Each symbol is run on its own. Positions in different symbols don't share buying power.

Tests: `tests/test_backtest.py` (target hit, stop hit, both in one candle, skip past target, crypto fees).

## Gold (GLD), the current setup (run 2026-11-26)

15-minute candles, swing length 3, $100 risk, TP5, regular hours, 0.02% slippage a side, no commission.

| Period | Trades | Win % | Net P&L | Avg R | Profit factor | Max drawdown | Targets (TP5) | Stops | Closed by a new signal | GLD price |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 365 days (2025-11-25 to 2026-11-25) | 241 | 45.6 | **+$1,169** | +0.05 | 1.05 | −$4,359 | 24 | 106 | 111 | −14.4% |
| 180 days (2026-05-29 to 2026-11-25) | 121 | 47.9 | **+$389** | +0.03 | 1.03 | −$4,359 | 14 | 53 | 54 | −22.1% |

About one trade every 1.5 trading days. "Win %" counts every trade closed in profit, including small gains when a new signal closes the trade early. Only about 1 in 10 trades reaches TP5.

What it means: on gold the strategy is **about break-even**. It made $1,169 in a year on $100 risk a trade (+0.05R a trade), while GLD itself fell 14%. The worst run of losses was $4,359, about 44 losing trades' worth, so expect long losing streaks. That edge is small enough that a slightly worse fill could cancel it.

## Earlier results (2026-11-25, before the gold switch)

BTC/USD, ETH/USD, and AAPL, run with the engine as it was on 2026-11-25 (strict swings on both sides, no `mintick`) and the TP2 target, so these numbers are only roughly comparable.

15-minute candles, $100 risk, TP2 unless noted. In this period BTC fell 18.6%, ETH fell 16.5%, and AAPL rose 13.8%.

| Variant | Trades | Win % | Net P&L | Avg R | Profit factor |
| --- | --- | --- | --- | --- | --- |
| **As the bot runs** (pivots 3/3) | 701 | 24.3 | **−$76,285** | −1.09 | 0.14 |
| Pivots 3/1 (the old `.env`) | 708 | 19.4 | −$106,078 | −1.50 | 0.09 |
| TP3 target | 701 | 22.8 | −$77,027 | −1.10 | 0.16 |
| 30-minute candles | 369 | 27.6 | −$28,471 | −0.77 | 0.22 |
| 30-minute, TP3 | 369 | 26.6 | −$27,787 | −0.75 | 0.26 |
| Hold through new signals | 319 | 28.5 | −$31,890 | −1.00 | 0.26 |
| **No fees or slippage** | 700 | 40.0 | −$4,824 | −0.07 | 0.87 |
| Hold, no fees or slippage | 318 | 33.0 | −$336 | −0.01 | 0.98 |

Per symbol, as the bot runs:

| Symbol | Trades | Win % | Net P&L | Avg R | Fees paid |
| --- | --- | --- | --- | --- | --- |
| BTC/USD | 305 | 20.0 | −$43,197 | −1.42 | $38,220 |
| ETH/USD | 291 | 23.0 | −$31,284 | −1.08 | $27,712 |
| AAPL | 105 | 40.0 | −$1,803 | −0.17 | $0 |

## What it means

1. **The strategy has no edge in this period, even with no costs.** Before fees it lost slightly in every variant. The best case, holding through new signals with no costs, broke even (profit factor 0.98).
2. **Fees make crypto lose heavily.** On 15-minute crypto candles the median stop is only **0.5%** (BTC) to **0.7%** (ETH) from entry, so $100 of risk means a position of about $15,000–20,000. Alpaca's 0.25% fee on the way in and out costs about $75–100 on that, close to a full 1R on every trade. Fees were about 88% of the crypto loss.
3. **AAPL is close to break-even** (no commission, 1.15% median stop) but still negative.
4. **Longer candles help** (wider stops, so fees weigh less), but not enough.

> [!warning]
> On crypto, expect the paper account to lose money. On GLD it was about break-even (see above). Don't move either to real money.

## Ideas worth testing

- **Higher timeframes** (1 hour, 4 hours): wider stops make fees a smaller share. The bot's data calls only take minutes (1–59) today.
- **A minimum stop distance**, e.g. skip crypto setups whose stop is under 1.5%, so one round trip of fees is at most about a third of R.
- **Stocks only**, or more stocks, where Alpaca charges no commission.
- **Trend filter**: in this period crypto fell steadily; only taking BUYs above a moving average (and SELLs below it) is a common fix for structure strategies.
- **More history** (`--days 365` or more) and other symbols before trusting any setting: 180 days is one market phase.
