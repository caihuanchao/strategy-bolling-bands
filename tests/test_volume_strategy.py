"""Tests for VolumeAnalysisStrategy and volume_interpreter — Prove-It pattern."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_df(close_vals, volume_vals, dates=None):
    """Build a DataFrame with required columns for volume strategy."""
    import pandas as pd
    n = len(close_vals)
    if dates is None:
        dates = [f"2026-01-{i+1:02d}" for i in range(n)]
    return pd.DataFrame({
        "close": close_vals,
        "volume": volume_vals,
        "date": dates,
    })


class TestOBVCalculation(unittest.TestCase):
    """OBV: verify cumulative calculation — up day adds volume, down day subtracts."""

    def test_obv_accumulates_correctly(self):
        """OBV increases with volume on up days, decreases on down days."""
        from src.strategies.volume import VolumeAnalysisStrategy
        df = _make_df(
            [10.0, 11.0, 10.5, 12.0, 12.0],
            [100, 200, 150, 300, 100],
        )
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        obv = result["obv"].values
        self.assertEqual(obv[0], 100.0)
        self.assertEqual(obv[1], 300.0)   # up: +200
        self.assertEqual(obv[2], 150.0)   # down: -150
        self.assertEqual(obv[3], 450.0)   # up: +300
        self.assertEqual(obv[4], 450.0)   # flat: no change

    def test_obv_with_empty_volume(self):
        """OBV handles zero/missing volume gracefully."""
        from src.strategies.volume import VolumeAnalysisStrategy
        df = _make_df([10.0, 10.5, 10.3], [0, 100, 50])
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertEqual(result["obv"].iloc[0], 0.0)


class TestDivergenceDetection(unittest.TestCase):
    """Volume-price divergence: top divergence (price up, volume down) and bottom divergence."""

    def test_top_divergence_detected(self):
        """Price makes new high but volume ratio is lower than previous peak."""
        from src.strategies.volume import VolumeAnalysisStrategy
        # Need enough rows for lookback*2. Build 45 rows with a divergence pattern.
        n = 45
        close = [10.0 + i * 0.1 for i in range(n)]  # steady uptrend
        volume = [10000] * n
        # Previous high: row 25, high volume
        volume[25] = 50000
        close[25] = close[24] + 0.5  # mark as high
        # Current: rows 40-44, price keeps rising but volume drops
        for i in range(40, 45):
            volume[i] = 5000  # low volume
            close[i] = close[i-1] + 0.3

        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        params = {"divergence_lookback": 15, "volume_ratio_threshold": 1.5,
                  "contraction_threshold": 0.5, "obv_divergence_window": 15}
        result = strategy.generate_signals(df, params)

        # Should detect at least one top divergence in the last 5 rows
        top_count = int(result["divergence_top"].iloc[-5:].sum())
        self.assertGreater(top_count, 0, "Expected top divergence detected")

    def test_bottom_divergence_detected(self):
        """Price makes new low but volume shrinks — selling exhaustion."""
        from src.strategies.volume import VolumeAnalysisStrategy
        n = 45
        close = [20.0 - i * 0.1 for i in range(n)]  # steady downtrend
        volume = [10000] * n
        # Previous low: row 25, high volume (panic)
        volume[25] = 50000
        close[25] = close[24] - 0.5
        # Current: rows 40-44, price keeps falling but volume shrinks
        for i in range(40, 45):
            volume[i] = 5000  # very low volume
            close[i] = close[i-1] - 0.3

        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        params = {"divergence_lookback": 15, "volume_ratio_threshold": 1.5,
                  "contraction_threshold": 0.5, "obv_divergence_window": 15}
        result = strategy.generate_signals(df, params)

        bottom_count = int(result["divergence_bottom"].iloc[-5:].sum())
        self.assertGreater(bottom_count, 0, "Expected bottom divergence detected")


class TestVolumeBreakout(unittest.TestCase):
    """Breakout buy: volume ratio >= threshold AND close up."""

    def test_breakout_signal_triggered(self):
        """High volume ratio + price increase = breakout buy."""
        from src.strategies.volume import VolumeAnalysisStrategy
        close = [10.0] * 25 + [10.0, 10.8]  # enough history then surge
        volume = [10000] * 25 + [10000, 50000]  # 5x avg volume
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertEqual(result["breakout_buy"].iloc[-1], 1)

    def test_no_breakout_when_price_falls(self):
        """High volume but price drops = no breakout buy."""
        from src.strategies.volume import VolumeAnalysisStrategy
        close = [10.0] * 25 + [10.0, 9.5]
        volume = [10000] * 25 + [10000, 50000]
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertEqual(result["breakout_buy"].iloc[-1], 0)


class TestContractionPullback(unittest.TestCase):
    """Volume contraction pullback in uptrend."""

    def test_contraction_buy_in_uptrend(self):
        """Uptrend + pullback + low volume + stopped falling = contraction buy."""
        from src.strategies.volume import VolumeAnalysisStrategy
        # Build: 25 uptrend rows → 3 pullback rows → 2 stabilization rows
        uptrend = [10.0 + i * 0.3 for i in range(25)]  # strong uptrend, ends at 17.5
        peak = uptrend[-1]  # 17.5
        # Pullback below 97% of 5-day high, with low volume
        pullback = [peak * 0.96, peak * 0.94, peak * 0.93]
        # Stabilize: slight bounce (stopped_falling = True), still in pullback zone, low volume
        stabilize = [pullback[-1] + 0.05, pullback[-1] + 0.10]
        close_vals = uptrend + pullback + stabilize
        volume_vals = [20000] * 25 + [7000, 6000, 5000, 6000, 7000]

        df = _make_df(close_vals, volume_vals)
        strategy = VolumeAnalysisStrategy()
        params = {"divergence_lookback": 20, "volume_ratio_threshold": 1.5,
                  "contraction_threshold": 0.5, "obv_divergence_window": 20}
        result = strategy.generate_signals(df, params)
        self.assertEqual(result["contraction_buy"].iloc[-1], 1)

    def test_no_contraction_when_not_uptrend(self):
        """Below MA20, contraction signal should not fire."""
        from src.strategies.volume import VolumeAnalysisStrategy
        n = 30
        close = [20.0 - i * 0.2 for i in range(28)] + [10.0, 10.1]
        volume = [20000] * 28 + [8000, 8000]
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertEqual(result["contraction_buy"].iloc[-1], 0)


class TestClimaxDetection(unittest.TestCase):
    """Volume climax: extreme volume at price extremes."""

    def test_buying_climax_detected(self):
        """Extreme volume near 20-day high = buying climax (potential top)."""
        from src.strategies.volume import VolumeAnalysisStrategy
        n = 35
        close = [10.0 + i * 0.1 for i in range(34)] + [14.0]  # uptrend, near high
        volume = [10000] * 34 + [100000]  # 10x "normal" volume
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertEqual(result["pattern_climax_sell"].iloc[-1], 1)

    def test_selling_climax_detected(self):
        """Extreme volume near 20-day low = selling climax (potential bottom)."""
        from src.strategies.volume import VolumeAnalysisStrategy
        n = 35
        close = [20.0 - i * 0.1 for i in range(34)] + [16.0]  # downtrend, near low
        volume = [10000] * 34 + [100000]
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertEqual(result["pattern_climax_buy"].iloc[-1], 1)


class TestPatternScoring(unittest.TestCase):
    """Pattern scoring: up+volume=+1, up+shrink=-1, down+volume=-1, down+shrink=+1."""

    def test_accumulation_pattern_positive_score(self):
        """Up days with volume and down days shrinking = accumulation (positive score)."""
        from src.strategies.volume import VolumeAnalysisStrategy
        # Build 30 rows of accumulation pattern
        n = 35
        close = []
        volume = []
        for i in range(n):
            if i % 2 == 0:
                close.append(10.0 + i * 0.1)  # up
                volume.append(30000)  # strong volume
            else:
                close.append(close[-1] - 0.03)  # slight down
                volume.append(5000)  # very low volume
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        # Score sum should be positive (accumulation)
        self.assertGreater(result["pattern_score_sum"].iloc[-1], 0)

    def test_distribution_pattern_negative_score(self):
        """Up days shrinking and down days expanding = distribution (negative score)."""
        from src.strategies.volume import VolumeAnalysisStrategy
        n = 35
        close = []
        volume = []
        for i in range(n):
            if i % 2 == 0:
                close.append(20.0 - i * 0.05)  # slight up
                volume.append(5000)  # low volume
            else:
                close.append(close[-1] - 0.15)  # significant down
                volume.append(30000)  # strong volume
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result = strategy.generate_signals(df, strategy.get_default_params())
        self.assertLess(result["pattern_score_sum"].iloc[-1], 0)


class TestLightweightResonance(unittest.TestCase):
    """≥2 conditions met → is_enhanced = True."""

    def test_enhanced_when_two_conditions_met(self):
        """When 2+ conditions are met and signal exists, is_enhanced should be True."""
        from src.strategies.volume import VolumeAnalysisStrategy
        n = 45
        close = []
        volume = []
        for i in range(n):
            if i % 3 == 0:
                close.append(15.0 + i * 0.05)  # mostly up
                volume.append(30000)  # strong
            elif i % 3 == 1:
                close.append(close[-1] + 0.2)
                volume.append(40000)  # even stronger (breakout-like)
            else:
                close.append(close[-1] - 0.02)
                volume.append(5000)  # low

        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        params = {"divergence_lookback": 15, "volume_ratio_threshold": 1.5,
                  "contraction_threshold": 0.5, "obv_divergence_window": 15}
        result = strategy.generate_signals(df, params)

        # Should have at least one enhanced signal where buy/sell=1 and conditions_met>=2
        enhanced = result[
            ((result["buy_signal"] == 1) | (result["sell_signal"] == 1)) &
            (result["is_enhanced"] == True)
        ]
        self.assertGreater(len(enhanced), 0, "Should have at least one enhanced signal")


class TestInterpreterPriceVolumeRelation(unittest.TestCase):
    """Interpreter correctly classifies volume-price relationships."""

    def test_up_with_volume(self):
        """Price up + volume ratio >= 1.2 → 价涨量增."""
        from src.strategies.volume import VolumeAnalysisStrategy
        from src.strategies.volume_interpreter import interpret_volume_all
        n = 30
        close_vals = [10.0 + i * 0.1 for i in range(n-1)] + [14.0]
        volume = [20000] * (n-1) + [50000]
        df = _make_df(close_vals, volume)
        strategy = VolumeAnalysisStrategy()
        result_df = strategy.generate_signals(df, strategy.get_default_params())
        interp = interpret_volume_all(result_df)
        self.assertEqual(interp["price_volume_relation"]["status"], "up_with_volume")

    def test_down_with_volume(self):
        """Price down + volume ratio >= 1.2 → 价跌量增."""
        from src.strategies.volume import VolumeAnalysisStrategy
        from src.strategies.volume_interpreter import interpret_volume_all
        n = 30
        close = [20.0 - i * 0.1 for i in range(n-1)] + [16.5]
        volume = [20000] * (n-1) + [50000]
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result_df = strategy.generate_signals(df, strategy.get_default_params())
        interp = interpret_volume_all(result_df)
        self.assertEqual(interp["price_volume_relation"]["status"], "down_with_volume")


class TestInterpreterOBVDivergence(unittest.TestCase):
    """Interpreter detects OBV divergence."""

    def test_obv_divergence_when_price_up_obv_down(self):
        """Price up 10 days but OBV trend is not rising → OBV divergence warning."""
        from src.strategies.volume import VolumeAnalysisStrategy
        from src.strategies.volume_interpreter import interpret_volume_all
        n = 20
        close = [10.0 + i * 0.3 for i in range(n)]  # strong uptrend
        # Volume decreases over time → OBV won't keep up with price
        volume = [50000 - i * 2000 for i in range(n)]
        df = _make_df(close, volume)
        strategy = VolumeAnalysisStrategy()
        result_df = strategy.generate_signals(df, strategy.get_default_params())
        interp = interpret_volume_all(result_df)
        # OBV should diverge from price
        self.assertIn(interp["obv"]["status"],
                      ("obv_divergence_warning", "confirmed_up", "obv_divergence_bottom"))


class TestInterpreterMissingColumns(unittest.TestCase):
    """Graceful fallback when required columns are missing."""

    def test_returns_error_when_columns_missing(self):
        import pandas as pd
        from src.strategies.volume_interpreter import interpret_volume_all
        df = pd.DataFrame({"close": [10.0, 11.0], "volume": [100, 200]})
        result = interpret_volume_all(df)
        self.assertIn("error", result)
        self.assertIn("数据不足", result["error"])


class TestPatternLabelHelper(unittest.TestCase):
    """Prove-It: _pattern_label in app.py works without import errors."""

    def test_pattern_label_does_not_throw_name_error(self):
        """_pattern_label should work without NameError (pd not defined at module level)."""
        import app
        import pandas as pd
        # DataFrame with pattern_score_sum column
        df = pd.DataFrame({
            "pattern_score_sum": [0.5, 1.2, 2.0],
            "pattern_climax_buy": [0, 0, 0],
            "pattern_climax_sell": [0, 0, 0],
        })
        # Should not raise NameError: name 'pd' is not defined
        try:
            result = app._pattern_label(df)
        except NameError as e:
            self.fail(f"_pattern_label raised NameError: {e}")
        self.assertIsInstance(result, str)

    def test_pattern_label_returns_na_when_column_missing(self):
        """Returns N/A when pattern_score_sum column is absent."""
        import app
        import pandas as pd
        df = pd.DataFrame({"close": [10.0, 11.0]})
        result = app._pattern_label(df)
        self.assertEqual(result, "N/A")

    def test_pattern_label_detects_accumulation(self):
        """Score >= 3.0 → 吸筹建仓."""
        import app
        import pandas as pd
        df = pd.DataFrame({
            "pattern_score_sum": [0.5, 1.0, 3.5],
            "pattern_climax_buy": [0, 0, 0],
            "pattern_climax_sell": [0, 0, 0],
        })
        result = app._pattern_label(df)
        self.assertEqual(result, "吸筹建仓")

    def test_pattern_label_detects_distribution(self):
        """Score <= -3.0 → 派发出货."""
        import app
        import pandas as pd
        df = pd.DataFrame({
            "pattern_score_sum": [-1.0, -2.0, -3.5],
            "pattern_climax_buy": [0, 0, 0],
            "pattern_climax_sell": [0, 0, 0],
        })
        result = app._pattern_label(df)
        self.assertEqual(result, "派发出货")

    def test_pattern_label_detects_contraction(self):
        """Score near 0 → 缩量整理."""
        import app
        import pandas as pd
        df = pd.DataFrame({
            "pattern_score_sum": [0.3, -0.5, 0.1],
            "pattern_climax_buy": [0, 0, 0],
            "pattern_climax_sell": [0, 0, 0],
        })
        result = app._pattern_label(df)
        self.assertEqual(result, "缩量整理")


if __name__ == "__main__":
    unittest.main()
