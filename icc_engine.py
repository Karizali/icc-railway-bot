import pandas as pd


def evaluate_icc_structure(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    min_tick: float = 0.0,
) -> dict | None:
    """
    Port of the "ICC Clean Structure" Pine Script (Source Code.txt).

    Evaluates a DataFrame with ['timestamp', 'high', 'low', 'close'] of closed
    candles, oldest first, and returns a trade signal dictionary if the latest
    bar triggers an ICC Continuation entry. With left == right it reproduces
    the indicator's `swingLen` setting.
    """
    n = len(df)
    if n < left + right + 2:
        return None

    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    closes = df["close"].astype(float).tolist()
    timestamps = df["timestamp"].tolist()

    def pivot_high(p: int) -> float | None:
        window = highs[p - left : p + right + 1]
        return highs[p] if highs[p] == max(window) and window.count(highs[p]) == 1 else None

    def pivot_low(p: int) -> float | None:
        window = lows[p - left : p + right + 1]
        return lows[p] if lows[p] == min(window) and window.count(lows[p]) == 1 else None

    # State: 0 = waiting, 1 = bullish indication, 2 = bullish correction found,
    #        3 = bearish indication, 4 = bearish correction found
    state = 0
    last_high = last_low = None
    last_high_bar = last_low_bar = -1
    indication_high = indication_low = None
    correction_low = correction_high = None
    triggered_signal = None

    for t in range(n):
        close = closes[t]

        # 1. Confirmed swings: a pivot at bar p is known `right` bars later (ta.pivothigh / ta.pivotlow)
        p = t - right
        ph = pivot_high(p) if p - left >= 0 else None
        pl = pivot_low(p) if p - left >= 0 else None
        if ph is not None:
            last_high, last_high_bar = ph, p
        if pl is not None:
            last_low, last_low_bar = pl, p

        # 2. Indication: a close that crosses the last swing high / low
        if t > 0 and last_high is not None and close > last_high and closes[t - 1] <= last_high:
            state = 1
            indication_high, indication_low = close, None
            correction_low = correction_high = None
        if t > 0 and last_low is not None and close < last_low and closes[t - 1] >= last_low:
            state = 3
            indication_low, indication_high = close, None
            correction_low = correction_high = None

        # 3. Correction: the first swing low (high) that forms after the broken swing
        if state == 1 and pl is not None and p > last_high_bar:
            correction_low = pl
            state = 2
        if state == 3 and ph is not None and p > last_low_bar:
            correction_high = ph
            state = 4

        # 4. Continuation: a close beyond the indication close
        if state == 2 and close > indication_high:
            risk = close - correction_low
            if risk > min_tick:
                if t == n - 1:
                    triggered_signal = _signal("BUY", timestamps[t], close, correction_low, risk)
                state = 0
        elif state == 4 and close < indication_low:
            risk = correction_high - close
            if risk > min_tick:
                if t == n - 1:
                    triggered_signal = _signal("SELL", timestamps[t], close, correction_high, -risk)
                state = 0

    return triggered_signal


def _signal(action: str, timestamp, entry: float, sl: float, risk: float) -> dict:
    """`risk` is signed: positive for a BUY, negative for a SELL."""
    signal = {
        "action": action,
        "timestamp": pd.Timestamp(timestamp).isoformat(),
        "Entry": round(entry, 6),
        "SL": round(sl, 6),
    }
    for r in range(1, 6):
        signal[f"TP{r}"] = round(entry + risk * r, 6)
    return signal
