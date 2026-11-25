---
tags: [icc-bot, trading]
---

# Trade Execution

`execute_paper_trade(symbol, signal)` in `main.py` turns a [[Signal Engine#Signal|signal]] into Alpaca **paper** orders. It runs in a worker thread.

## Checks before any order

1. **Already placed?** The entry's `client_order_id` is `icc-<SYMBOL>-<BUY|SELL>-<candle epoch>`. If Alpaca already has an order with that id, the signal was traded before a restart and is skipped. (Alpaca also refuses a second order with the same id.)
2. **Crypto SELL**: close the long if there is one, otherwise skip. Spot crypto can't be shorted.
3. **Stocks**: skip if the market is closed.
4. **Price still valid**: the latest trade must still be between SL and the target. If price already ran past either, skip.
5. **Shortable**: a stock SELL is skipped if Alpaca can't short it.

## Position size

```text
qty = RISK_PER_TRADE_USD / |latest price − SL|
```

The latest price is used rather than the signal's `Entry`, so the dollar risk holds for the price actually paid. Then:

- capped at 95% of buying power (cash, `non_marginable_buying_power`, for crypto), with a log line when it bites;
- crypto: rounded **down** to the asset's `min_trade_increment`, skipped below `min_order_size`;
- stocks: rounded down to whole shares, **skipped if under 1 share** (it would risk more than the budget).

## Closing what was there

`flatten(symbol)` runs before every entry and on a crypto SELL: cancel all the symbol's open orders (old bracket legs, an old crypto stop), close the position, and wait until Alpaca shows it gone. Without the cancel, old bracket legs would hold the shares and could later fire against the new position.

## Stocks: bracket order

A market order, `GTC`, with `order_class=BRACKET`: take profit is a limit at the target and stop loss is a stop at `SL`, both rounded to cents. Alpaca manages the exit and cancels the other leg.

## Crypto: stop on Alpaca, target watched by the bot

Alpaca has no bracket orders for crypto, so:

1. Market BUY, `GTC`; wait for the fill (up to 30 s).
2. Read the position's `qty_available` (Alpaca takes its fee in the coin, so it is a little less than ordered).
3. Place a **stop-limit SELL** for that quantity: stop at `SL`, limit 0.5% below it. Its `client_order_id` is `icc-sl-<SYMBOL>-<epoch>-tp<target>`, which **stores the target on Alpaca**.
4. If the stop can't be placed, the position is closed at once. A crypto position is never left without a stop.

Every scan, `manage_crypto_exit` finds that stop order, reads the target from its id, and if the latest price has reached it, cancels the stop and closes the position (`TAKE PROFIT` in the log). If the stop filled, there is no position and nothing to do; a stop left over with no position is cancelled.

Because the stop rests on Alpaca, it still protects the position while the bot is down. The target only works while the bot runs.

## Tested on the paper account (2026-11-25)

With $5 risk: a BTC/USD buy, its stop-limit (for the held quantity after fees), the target read back from the order id, and the cleanup; an AAPL bracket, with both legs cancelled when the position closed; the same signal sent twice (skipped the second time); a crypto SELL with no position (skipped).

## Log lines

```
EXECUTED BUY 0.008345684 BTC/USD | ~59911.2 (signal 59911.2) | SL=59312.088 | TP2=61109.424 | ID=...
TAKE PROFIT BTC/USD at ~61120.0 (target 61109.424).
Closed long BTC/USD on ICC SELL signal.
Skipping AAPL BUY: price 352.1 is already outside SL 345.9 / TP2 366.2.
```
