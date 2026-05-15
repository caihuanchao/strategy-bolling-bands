"""Tests for dual_ma_interpreter — Prove-It pattern for strategy-aware interpretation."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_df(ema_fast_vals, ema_slow_vals, close_vals, volume_ratio_vals=None,
             buy_signals=None, sell_signals=None, volume_vals=None):
    """Build a DataFrame with required columns for dual_ma_interpreter."""
    import pandas as pd
    n = len(ema_fast_vals)
    data = {
        "ema_fast": ema_fast_vals,
        "ema_slow": ema_slow_vals,
        "close": close_vals,
        "volume_ratio": volume_ratio_vals or [1.5] * n,
        "buy_signal": buy_signals or [0] * n,
        "sell_signal": sell_signals or [0] * n,
        "volume": volume_vals or [200000] * n,
    }
    return pd.DataFrame(data)


class TestInterpretCross(unittest.TestCase):
    """Cross signal detection: golden cross, death cross, neutral."""

    def test_golden_cross_detected(self):
        """When ema_fast crosses above ema_slow, should detect golden cross."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [9.0, 10.0, 11.0],
            [9.5, 10.5, 10.5],
            [10.0, 10.5, 11.2],
            buy_signals=[0, 0, 1],
        )
        result = interpret_dual_ma_all(df)
        cross = result["cross_signal"]
        self.assertEqual(cross["status"], "golden_cross")
        self.assertIn("金叉", cross["status_label"])

    def test_death_cross_detected(self):
        """When ema_fast crosses below ema_slow, should detect death cross."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [11.0, 10.0, 9.0],
            [10.5, 9.5, 9.5],
            [10.5, 10.0, 9.0],
            sell_signals=[0, 0, 1],
        )
        result = interpret_dual_ma_all(df)
        cross = result["cross_signal"]
        self.assertEqual(cross["status"], "death_cross")
        self.assertIn("死叉", cross["status_label"])

    def test_no_cross_when_no_crossover(self):
        """When ema_fast stays above ema_slow, no cross detected."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [12.0, 12.5, 13.0],
            [10.0, 10.0, 10.0],
            [12.0, 12.5, 13.0],
        )
        result = interpret_dual_ma_all(df)
        self.assertEqual(result["cross_signal"]["status"], "golden_cross")
        self.assertEqual(result["cross_signal"]["last_cross"], "none")


class TestInterpretTrend(unittest.TestCase):
    """Trend direction and alignment detection."""

    def test_bullish_alignment(self):
        """Price > ema_fast > ema_slow = bullish alignment."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [10.0, 10.1, 10.2, 10.3, 10.4],
            [9.0, 9.0, 9.0, 9.0, 9.0],
            [11.0, 11.0, 11.0, 11.0, 11.0],
        )
        result = interpret_dual_ma_all(df)
        self.assertEqual(result["trend"]["alignment"], "bullish")
        self.assertIn("多头排列", result["trend"]["alignment_label"])

    def test_bearish_alignment(self):
        """Price < ema_fast < ema_slow = bearish alignment."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [9.0, 9.0, 9.0, 9.0, 9.0],
            [10.0, 10.1, 10.2, 10.3, 10.4],
            [8.0, 8.0, 8.0, 8.0, 8.0],
        )
        result = interpret_dual_ma_all(df)
        self.assertEqual(result["trend"]["alignment"], "bearish")
        self.assertIn("空头排列", result["trend"]["alignment_label"])


class TestInterpretReliability(unittest.TestCase):
    """Signal reliability rating per the 4-level guide system."""

    def test_strong_reliability_all_conditions_met(self):
        """All 4 conditions (cross, trend, price, volume) = strong (★★★★☆)."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [9.0, 10.0, 11.0, 12.0, 13.0],
            [9.5, 10.5, 10.5, 10.5, 10.5],
            [11.0, 12.0, 13.0, 14.0, 15.0],
            volume_ratio_vals=[1.8] * 5,
            buy_signals=[0, 0, 0, 0, 1],
        )
        result = interpret_dual_ma_all(df)
        rel = result["reliability"]
        self.assertEqual(rel["level"], "strong")
        self.assertEqual(rel["stars"], "★★★★☆")

    def test_weak_reliability_bare_cross_only(self):
        """Only cross with no trend/price/volume = weak or no_signal (≤2 stars)."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        # 7 rows: fast EMA rises from below to slightly above slow. Slow EMA is flat.
        # close stays below both EMAs. volume_ratio is tiny. This should yield ≤2 conditions.
        df = _make_df(
            [12.0, 11.5, 10.5, 10.0, 10.3, 10.6, 11.0],   # fast dips then crosses up
            [10.5, 10.5, 10.5, 10.5, 10.5, 10.5, 10.5],   # flat slow EMA
            [9.0, 8.5, 9.0, 7.0, 8.5, 9.0, 9.5],          # price stuck below both
            volume_ratio_vals=[0.4] * 7,                    # extremely low volume
            buy_signals=[0, 0, 0, 0, 0, 0, 1],
        )
        result = interpret_dual_ma_all(df)
        rel = result["reliability"]
        self.assertIn(rel["level"], ("weak", "no_signal"),
                      f"Expected weak/no_signal, got {rel['level']}")

    def test_death_cross_with_bearish_trend_is_strong(self):
        """Death cross + bearish alignment + volume = high reliability."""
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [11.0, 10.0, 9.5, 9.0, 8.5],
            [10.0, 9.5, 9.5, 9.5, 9.5],
            [9.0, 8.5, 8.0, 7.5, 7.0],
            volume_ratio_vals=[2.0] * 5,
            sell_signals=[0, 0, 0, 0, 1],
        )
        result = interpret_dual_ma_all(df)
        rel = result["reliability"]
        self.assertEqual(rel["level"], "strong")


class TestInterpretVolume(unittest.TestCase):
    """Volume confirmation analysis."""

    def test_volume_confirmed_when_ratio_above_threshold(self):
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [10.0] * 5, [9.0] * 5, [11.0] * 5,
            volume_ratio_vals=[1.8] * 5,
        )
        result = interpret_dual_ma_all(df)
        self.assertTrue(result["volume"]["is_confirmed"])

    def test_volume_not_confirmed_when_ratio_below_threshold(self):
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = _make_df(
            [10.0] * 5, [9.0] * 5, [11.0] * 5,
            volume_ratio_vals=[0.5] * 5,
        )
        result = interpret_dual_ma_all(df)
        self.assertFalse(result["volume"]["is_confirmed"])


class TestDataInsufficient(unittest.TestCase):
    """Graceful fallback when columns are missing."""

    def test_returns_error_when_ema_columns_missing(self):
        import pandas as pd
        from src.strategies.dual_ma_interpreter import interpret_dual_ma_all
        df = pd.DataFrame({"close": [10.0, 11.0], "volume": [100, 200]})
        result = interpret_dual_ma_all(df)
        self.assertIn("error", result)
        self.assertIn("数据不足", result["error"])


if __name__ == "__main__":
    unittest.main()
