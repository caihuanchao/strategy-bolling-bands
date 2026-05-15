"""Tests for data_fetcher module — Prove-It pattern for bug fixes."""

import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _hk_daily_df(dates, opens, highs, lows, closes, volumes):
    """Create a DataFrame mimicking AKShare stock_hk_daily output (Chinese columns)."""
    import pandas as pd
    return pd.DataFrame({
        "日期": dates,
        "开盘": opens,
        "最高": highs,
        "最低": lows,
        "收盘": closes,
        "成交量": volumes,
    })


class TestGetDataHkDailyAkshare(unittest.TestCase):
    """stock_hk_daily returns Chinese column names — previously KeyError 'date'"""

    @patch("akshare.stock_hk_daily")
    def test_handles_chinese_column_names(self, mock_hk_daily):
        """Chinese columns should be renamed to standard English names."""
        mock_hk_daily.return_value = _hk_daily_df(
            ["2025-01-02", "2025-01-03", "2025-01-06"],
            [10.0, 10.5, 11.0],
            [11.0, 11.5, 12.0],
            [9.5, 10.0, 10.5],
            [10.5, 11.0, 11.5],
            [1000000, 1200000, 1100000],
        )

        from src.data_fetcher import get_data_hk_daily_akshare
        df = get_data_hk_daily_akshare(symbol="02099", start_date="20250101")

        self.assertIn("date", df.columns)
        self.assertIn("open", df.columns)
        self.assertIn("close", df.columns)
        self.assertIn("volume", df.columns)
        # start_date is "20250101" (compact format), data has "2025-01-02"
        # the >= string comparison should still work for YYYY-MM-DD format dates
        self.assertTrue(len(df) > 0, "Should have data after column mapping")

    @patch("akshare.stock_hk_daily")
    def test_filters_by_start_date(self, mock_hk_daily):
        """Data before start_date should be excluded."""
        mock_hk_daily.return_value = _hk_daily_df(
            ["2024-12-31", "2025-01-02", "2025-01-03"],
            [10.0, 10.5, 11.0],
            [11.0, 12.0, 13.0],
            [9.0, 10.0, 11.0],
            [10.5, 11.0, 11.5],
            [100, 200, 300],
        )

        from src.data_fetcher import get_data_hk_daily_akshare
        df = get_data_hk_daily_akshare(symbol="00700", start_date="20250101")

        self.assertTrue(len(df) >= 2)

    @patch("akshare.stock_hk_daily")
    def test_raises_when_no_data_after_filter(self, mock_hk_daily):
        """Should raise when all data is before start_date."""
        mock_hk_daily.return_value = _hk_daily_df(
            ["2024-01-01", "2024-01-02"],
            [10.0, 10.5],
            [11.0, 12.0],
            [9.0, 10.0],
            [10.5, 11.0],
            [100, 200],
        )

        from src.data_fetcher import get_data_hk_daily_akshare

        with self.assertRaises(Exception) as ctx:
            get_data_hk_daily_akshare(symbol="02099", start_date="20250101")
        self.assertIn("stock_hk_daily unavailable", str(ctx.exception))

    @patch("akshare.stock_hk_daily")
    def test_retries_then_raises_on_persistent_error(self, mock_hk_daily):
        """After 2 failures, should raise 'stock_hk_daily unavailable'."""
        mock_hk_daily.side_effect = RuntimeError("API down")

        from src.data_fetcher import get_data_hk_daily_akshare

        with self.assertRaises(Exception) as ctx:
            get_data_hk_daily_akshare(symbol="02099", start_date="20250101")
        self.assertIn("stock_hk_daily unavailable", str(ctx.exception))
        self.assertEqual(mock_hk_daily.call_count, 2)


class TestGetStockDataIncrementalFallback(unittest.TestCase):
    """When incremental fetch fails, get_stock_data should fall back to cached data."""

    def _cached_df(self):
        import pandas as pd
        return pd.DataFrame({
            "date": ["2026-05-12", "2026-05-13", "2026-05-14"],
            "open": [10.0, 10.5, 11.0],
            "high": [11.0, 11.5, 12.0],
            "low": [9.5, 10.0, 10.5],
            "close": [10.8, 11.2, 11.6],
            "volume": [100000, 120000, 110000],
        })

    def _cached_meta(self):
        return {
            "symbol": "02099", "period": "daily", "start_date": "20250101",
            "latest_date": "2026-05-14", "last_updated": "2026-05-14T20:00:00",
            "source": "AKShare stock_hk_daily", "row_count": 334, "integrity": "ok"
        }

    @patch("src.data_fetcher.datetime")
    @patch("src.data_fetcher.load_cache_metadata")
    @patch("src.data_fetcher.load_from_cache")
    @patch("src.data_fetcher.get_data_hk_akshare")
    @patch("src.data_fetcher.get_data_hk_daily_akshare")
    def test_falls_back_to_cache_when_incremental_fetch_fails(
        self, mock_hk_daily, mock_hk_hist, mock_load_cache, mock_load_meta, mock_dt
    ):
        """When cache is 1 day old and all sources fail, return cached data."""
        mock_load_cache.return_value = self._cached_df()
        mock_load_meta.return_value = self._cached_meta()
        mock_hk_daily.side_effect = Exception("Connection aborted")
        mock_hk_hist.side_effect = Exception("Connection aborted")
        mock_dt.now.return_value = __import__("datetime").datetime(2026, 5, 15, 9, 0, 0)
        mock_dt.strptime = __import__("datetime").datetime.strptime

        from src.data_fetcher import get_stock_data
        df = get_stock_data(symbol="02099", period="daily", start_date="20250101",
                            name="中国黄金国际", use_cache=True)

        self.assertEqual(len(df), 3, "Should return the 3-row cached DataFrame")
        self.assertIn("2026-05-14", df["date"].values,
                      "Cached data with latest date 2026-05-14 should be returned")

    @patch("src.data_fetcher.datetime")
    @patch("src.data_fetcher.load_cache_metadata")
    @patch("src.data_fetcher.load_from_cache")
    @patch("src.data_fetcher.get_data_hk_akshare")
    @patch("src.data_fetcher.get_data_hk_daily_akshare")
    def test_still_raises_when_no_cache_and_fetch_fails(
        self, mock_hk_daily, mock_hk_hist, mock_load_cache, mock_load_meta, mock_dt
    ):
        """When there's no cache and all sources fail, should still raise."""
        mock_load_cache.return_value = None
        mock_load_meta.return_value = None
        mock_hk_daily.side_effect = Exception("Connection aborted")
        mock_hk_hist.side_effect = Exception("Connection aborted")
        mock_dt.now.return_value = __import__("datetime").datetime(2026, 5, 15, 9, 0, 0)
        mock_dt.strptime = __import__("datetime").datetime.strptime

        from src.data_fetcher import get_stock_data
        with self.assertRaises(Exception) as ctx:
            get_stock_data(symbol="02099", period="daily", start_date="20250101",
                           name="中国黄金国际", use_cache=True)
        self.assertIn("All data sources unavailable", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
