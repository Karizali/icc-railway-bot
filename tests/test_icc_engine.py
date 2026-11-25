import unittest

import pandas as pd

from icc_engine import evaluate_icc_structure


def bars(closes: list[float]) -> pd.DataFrame:
    # Flat candles (high = low = close) keep the swings easy to read
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=len(closes), freq="15min", tz="UTC"),
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
        }
    )


# Swing high 12 at bar 2 (confirmed bar 4), break to 13 at bar 5 (indication = 13),
# swing low 10 at bar 4 (confirmed bar 6, after the broken high), close 14 > 13 (continuation).
BULL = [10, 11, 12, 11, 10, 13, 14]
BEAR = [30 - c for c in BULL]


class IccEngineTest(unittest.TestCase):
    def test_bullish_continuation_on_last_bar(self):
        signal = evaluate_icc_structure(bars(BULL), left=2, right=2)
        self.assertEqual(signal["action"], "BUY")
        self.assertEqual(signal["Entry"], 14)
        self.assertEqual(signal["SL"], 10)
        self.assertEqual([signal[f"TP{r}"] for r in range(1, 6)], [18, 22, 26, 30, 34])
        self.assertEqual(signal["timestamp"], "2026-01-01T01:30:00+00:00")

    def test_bearish_continuation_on_last_bar(self):
        signal = evaluate_icc_structure(bars(BEAR), left=2, right=2)
        self.assertEqual(signal["action"], "SELL")
        self.assertEqual(signal["Entry"], 16)
        self.assertEqual(signal["SL"], 20)
        self.assertEqual(signal["TP2"], 8)

    def test_indication_alone_is_not_a_signal(self):
        self.assertIsNone(evaluate_icc_structure(bars(BULL[:-1]), left=2, right=2))

    def test_signal_on_an_older_bar_is_not_returned(self):
        self.assertIsNone(evaluate_icc_structure(bars(BULL + [15]), left=2, right=2))

    def test_continuation_must_beat_the_indication_close(self):
        # 12.5 is above the broken swing high (12) but not above the indication close (13)
        self.assertIsNone(evaluate_icc_structure(bars(BULL[:-1] + [12.5]), left=2, right=2))

    def test_a_new_break_restarts_the_setup(self):
        # After the BUY, a new swing high 15 forms and breaks at 15.5: indication only, no entry
        closes = BULL + [15, 14.5, 14, 15.5]
        self.assertIsNone(evaluate_icc_structure(bars(closes), left=2, right=2))

    def test_equal_high_on_the_left_is_still_a_swing(self):
        # ta.pivothigh: the newest of two equal highs is the pivot (bar 2 here)
        signal = evaluate_icc_structure(bars([10, 12, 12, 11, 10, 13, 14]), left=2, right=2)
        self.assertEqual((signal["action"], signal["Entry"], signal["SL"]), ("BUY", 14, 10))

    def test_equal_high_on_the_right_cancels_the_swing(self):
        self.assertIsNone(evaluate_icc_structure(bars([10, 11, 12, 12, 10, 13, 14]), left=2, right=2))

    def test_risk_must_exceed_min_tick_and_the_setup_stays_armed(self):
        # Risk 4 is not above a 5 tick: no alert, state stays 2, and the next close (risk 6) fires
        self.assertIsNone(evaluate_icc_structure(bars(BULL), left=2, right=2, min_tick=5))
        signal = evaluate_icc_structure(bars(BULL + [16]), left=2, right=2, min_tick=5)
        self.assertEqual((signal["action"], signal["Entry"], signal["SL"]), ("BUY", 16, 10))

    def test_too_few_bars(self):
        self.assertIsNone(evaluate_icc_structure(bars(BULL[:5]), left=2, right=2))


if __name__ == "__main__":
    unittest.main()
