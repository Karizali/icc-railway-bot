import pandas as pd


def icc_signals(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    min_tick: float = 0.0,
) -> list[dict]:
    """
    Port of the "ICC Clean Structure" Pine Script (Source Code.txt), run over the
    whole DataFrame the way TradingView runs it over a chart's history.

    `df` holds closed candles, oldest first, with ['timestamp', 'high', 'low', 'close'].
    Returns every alert the indicator would fire (BUY / SELL with Entry, SL, TP1-TP5),
    each with `bar` (its row in `df`). With left == right this is the indicator's
    `swingLen`; `min_tick` is `syminfo.mintick`.
    """
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    closes = df["close"].astype(float).tolist()
    timestamps = df["timestamp"].tolist()
    n = len(closes)

    # ta.pivothigh / ta.pivotlow: the newest bar wins a tie, so the pivot must beat
    # every bar on its right strictly and match or beat every bar on its left.
    def pivot_high(p: int) -> float | None:
        h = highs[p]
        if all(x <= h for x in highs[p - left : p]) and all(x < h for x in highs[p + 1 : p + right + 1]):
            return h
        return None

    def pivot_low(p: int) -> float | None:
        lo = lows[p]
        if all(x >= lo for x in lows[p - left : p]) and all(x > lo for x in lows[p + 1 : p + right + 1]):
            return lo
        return None

    # var int state: 0 = waiting, 1 = bullish indication, 2 = bullish correction found,
    #                3 = bearish indication, 4 = bearish correction found
    state = 0
    last_high = last_low = None  # lastHigh / lastLow
    last_high_bar = last_low_bar = -1  # nz(lastHighBar, -1) / nz(lastLowBar, -1)
    indication_high = indication_low = None
    correction_low = correction_high = None
    signals = []

    for t in range(n):
        close = closes[t]

        # CONFIRMED SWINGS: a pivot at bar p is reported `right` bars later
        p = t - right
        ph = pivot_high(p) if p - left >= 0 else None
        pl = pivot_low(p) if p - left >= 0 else None
        if ph is not None:
            last_high, last_high_bar = ph, p
        if pl is not None:
            last_low, last_low_bar = pl, p

        # INDICATION: bullBreak / bearBreak (close[1] is na on the first bar)
        if t > 0 and last_high is not None and close > last_high and closes[t - 1] <= last_high:
            state = 1
            indication_high, indication_low = close, None
            correction_low = correction_high = None
        if t > 0 and last_low is not None and close < last_low and closes[t - 1] >= last_low:
            state = 3
            indication_low, indication_high = close, None
            correction_low = correction_high = None

        # ICC CORRECTION: bar_index - swingLen > nz(lastHighBar, -1)
        if state == 1 and pl is not None and p > last_high_bar:
            correction_low = pl
            state = 2
        if state == 3 and ph is not None and p > last_low_bar:
            correction_high = ph
            state = 4

        # ICC CONTINUATION / ENTRY: buySignal / sellSignal, then `if risk > syminfo.mintick`
        # (the alert and `state := 0` happen only inside that check)
        if state == 2 and close > indication_high:
            risk = close - correction_low
            if risk > min_tick:
                signals.append(_signal("BUY", t, timestamps[t], close, correction_low, risk))
                state = 0
        elif state == 4 and close < indication_low:
            risk = correction_high - close
            if risk > min_tick:
                signals.append(_signal("SELL", t, timestamps[t], close, correction_high, -risk))
                state = 0

    return signals


def evaluate_icc_structure(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    min_tick: float = 0.0,
) -> dict | None:
    """The alert fired on the last (latest closed) candle of `df`, if any."""
    if len(df) < left + right + 2:
        return None
    signals = icc_signals(df, left, right, min_tick)
    if signals and signals[-1]["bar"] == len(df) - 1:
        return signals[-1]
    return None


def _signal(action: str, bar: int, timestamp, entry: float, sl: float, risk: float) -> dict:
    """`risk` is signed: positive for a BUY, negative for a SELL (tp = entry + risk * rr)."""
    signal = {
        "action": action,
        "bar": bar,
        "timestamp": pd.Timestamp(timestamp).isoformat(),
        "Entry": round(entry, 6),
        "SL": round(sl, 6),
    }
    for r in range(1, 6):
        signal[f"TP{r}"] = round(entry + risk * r, 6)
    return signal
