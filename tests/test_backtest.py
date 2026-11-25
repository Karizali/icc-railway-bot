import unittest

import pandas as pd

from backtest import Config, simulate
from tests.test_icc_engine import BULL


def candles(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=len(rows), freq="15min", tz="UTC"),
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
        }
    )


# BULL signals BUY on its last candle: entry 14, SL 10, so TP2 = 22.
SETUP = [(c, c, c, c) for c in BULL]
CFG = Config(left=2, right=2, lookback=len(BULL), risk_usd=100, target="TP2", crypto_fee=0, slippage=0)


class SimulateTest(unittest.TestCase):
    def test_long_reaches_target(self):
        # Enter at the next open (14.5); the third candle trades through 22
        df = candles(SETUP + [(14.5, 16, 14.5, 16), (16, 19, 16, 19), (19, 23, 19, 23)])
        [trade] = simulate("AAPL", df, CFG)
        self.assertEqual((trade.side, trade.entry, trade.reason, trade.exit), ("BUY", 14.5, "target", 22))
        self.assertEqual(trade.qty, 22)  # int(100 / (14.5 - 10))
        self.assertEqual(trade.pnl, 165.0)  # 22 shares × 7.5

    def test_long_stopped_out(self):
        df = candles(SETUP + [(14.5, 15, 13, 13), (13, 13, 9, 9)])
        [trade] = simulate("AAPL", df, CFG)
        self.assertEqual((trade.reason, trade.exit, trade.pnl), ("stop loss", 10, -99.0))

    def test_stop_comes_first_when_a_candle_touches_both(self):
        df = candles(SETUP + [(14.5, 23, 9, 15)])
        [trade] = simulate("AAPL", df, CFG)
        self.assertEqual(trade.reason, "stop loss")

    def test_skipped_when_price_opens_past_the_target(self):
        df = candles(SETUP + [(23, 24, 23, 24)])
        self.assertEqual(simulate("AAPL", df, CFG), [])

    def test_crypto_pays_fees(self):
        df = candles(SETUP + [(14.5, 16, 14.5, 16), (16, 19, 16, 19), (19, 23, 19, 23)])
        [trade] = simulate("BTC/USD", df, Config(**{**CFG.__dict__, "crypto_fee": 0.01}))
        # 22.222222 coins × 7.5 gain, minus 1% of (14.5 + 22) × qty
        self.assertAlmostEqual(trade.pnl, 166.67 - 8.11, places=2)


if __name__ == "__main__":
    unittest.main()
