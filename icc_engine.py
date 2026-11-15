import pandas as pd
import numpy as np


def evaluate_icc_structure(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 1,
    min_rr_buffer: float = 0.001,
) -> dict | None:
    """
    Evaluates a DataFrame with ['timestamp', 'open', 'high', 'low', 'close']
    and returns a trade signal dictionary if the latest closed bar triggers an
    ICC Continuation entry.
    """
    if len(df) < (left + right + 10):
        return None

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    timestamps = df["timestamp"].values

    pivots = []  # list of dicts: {idx, price, type: 'H'|'L', label: 'HH'|'LH'|'HL'|'LL'}
    last_high = None
    last_low = None

    # 1. Detect confirmed swing highs and swing lows (matching Pine ta.pivothigh / ta.pivotlow)
    for i in range(left, len(df) - right):
        window_high = highs[i - left : i + right + 1]
        if highs[i] == np.max(window_high) and np.sum(window_high == highs[i]) == 1:
            label = "HH" if (last_high is None or highs[i] > last_high) else "LH"
            last_high = highs[i]
            pivots.append({"idx": i, "price": float(highs[i]), "type": "H", "label": label})

        window_low = lows[i - left : i + right + 1]
        if lows[i] == np.min(window_low) and np.sum(window_low == lows[i]) == 1:
            label = "HL" if (last_low is None or lows[i] > last_low) else "LL"
            last_low = lows[i]
            pivots.append({"idx": i, "price": float(lows[i]), "type": "L", "label": label})

    if len(pivots) < 4:
        return None

    # 2. Walk the Indication -> Correction -> Continuation (ICC) State Machine
    # Bullish ICC: Indication (HH) -> Correction (HL) -> Continuation (close > Indication HH)
    # Bearish ICC: Indication (LL) -> Correction (LH) -> Continuation (close < Indication LL)
    state = "NEUTRAL"
    indication_price = None
    correction_price = None
    setup_bar_idx = None
    triggered_signal = None

    latest_closed_idx = len(df) - 1

    for bar_idx in range(left + right, len(df)):
        # Check pivots confirmed on this bar (confirmed `right` bars after pivot)
        newly_confirmed = [p for p in pivots if p["idx"] + right == bar_idx]

        for p in newly_confirmed:
            if p["label"] == "HH":
                state = "BULL_INDICATION"
                indication_price = p["price"]
                correction_price = None
                setup_bar_idx = bar_idx
            elif p["label"] == "HL" and state == "BULL_INDICATION":
                if p["price"] < indication_price:
                    state = "BULL_CORRECTION"
                    correction_price = p["price"]
            elif p["label"] == "LL":
                state = "BEAR_INDICATION"
                indication_price = p["price"]
                correction_price = None
                setup_bar_idx = bar_idx
            elif p["label"] == "LH" and state == "BEAR_INDICATION":
                if p["price"] > indication_price:
                    state = "BEAR_CORRECTION"
                    correction_price = p["price"]

        close_price = float(closes[bar_idx])

        # Continuation trigger on bar close
        if state == "BULL_CORRECTION" and correction_price is not None:
            if close_price < correction_price:
                # Structure invalidated
                state = "NEUTRAL"
            elif close_price > indication_price:
                sl = correction_price * (1.0 - min_rr_buffer)
                risk = close_price - sl
                if risk > 0 and bar_idx == latest_closed_idx:
                    triggered_signal = {
                        "action": "BUY",
                        "timestamp": str(timestamps[bar_idx]),
                        "Entry": round(close_price, 4),
                        "SL": round(sl, 4),
                        "TP1": round(close_price + risk * 1.0, 4),
                        "TP2": round(close_price + risk * 2.0, 4),
                        "TP3": round(close_price + risk * 3.0, 4),
                        "TP4": round(close_price + risk * 4.0, 4),
                        "TP5": round(close_price + risk * 5.0, 4),
                    }
                state = "NEUTRAL"

        elif state == "BEAR_CORRECTION" and correction_price is not None:
            if close_price > correction_price:
                # Structure invalidated
                state = "NEUTRAL"
            elif close_price < indication_price:
                sl = correction_price * (1.0 + min_rr_buffer)
                risk = sl - close_price
                if risk > 0 and bar_idx == latest_closed_idx:
                    triggered_signal = {
                        "action": "SELL",
                        "timestamp": str(timestamps[bar_idx]),
                        "Entry": round(close_price, 4),
                        "SL": round(sl, 4),
                        "TP1": round(close_price - risk * 1.0, 4),
                        "TP2": round(close_price - risk * 2.0, 4),
                        "TP3": round(close_price - risk * 3.0, 4),
                        "TP4": round(close_price - risk * 4.0, 4),
                        "TP5": round(close_price - risk * 5.0, 4),
                    }
                state = "NEUTRAL"

    return triggered_signal