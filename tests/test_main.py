"""
test_main.py – Integration-level tests for the main pipeline.

These tests mock yfinance calls so they run offline.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import yaml

from src.main import fetch_ticker_data, run
from src.utils import setup_logging, load_config


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────

def _mock_history(*args, **kwargs):
    """Return a small synthetic DataFrame mimicking yf.Ticker.history()."""
    dates = pd.date_range("2024-01-02", periods=20, freq="B")
    close = 150 + np.cumsum(np.random.default_rng(0).standard_normal(20)).round(2)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.random.default_rng(0).integers(1_000_000, 5_000_000, size=20),
        },
        index=dates,
    )


def _mock_info():
    return {
        "shortName": "Mock Corp",
        "sector": "Tech",
        "industry": "Software",
        "marketCap": 1_000_000_000,
        "trailingPE": 25.0,
        "forwardPE": 22.0,
        "trailingEps": 4.0,
        "dividendYield": 0.01,
        "fiftyTwoWeekHigh": 200.0,
        "fiftyTwoWeekLow": 100.0,
        "averageVolume": 10_000_000,
        "beta": 1.1,
    }


# ────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────

class TestFetchTickerData:
    @patch("src.main.yf.Ticker")
    def test_returns_all_keys(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history = _mock_history
        mock_ticker.info = _mock_info()
        mock_ticker.quarterly_financials = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        import logging
        logger = logging.getLogger("test")

        result = fetch_ticker_data("MOCK", "2024-01-01", "2024-06-30", [5, 10], logger)

        assert "historical" in result
        assert "metrics" in result
        assert "earnings" in result
        assert not result["historical"].empty
        assert result["metrics"]["Name"] == "Mock Corp"


class TestRunPipeline:
    @patch("src.main.yf.Ticker")
    def test_full_pipeline_csv(self, mock_ticker_cls, tmp_path):
        """End-to-end: config → fetch (mocked) → export CSV files."""
        mock_ticker = MagicMock()
        mock_ticker.history = _mock_history
        mock_ticker.info = _mock_info()
        mock_ticker.quarterly_financials = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        # Write a temp config
        cfg = {
            "tickers": ["MOCK"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "moving_averages": [5],
            "output": {
                "directory": str(tmp_path / "output"),
                "format": "csv",
                "summary_report": True,
            },
            "logging": {
                "level": "DEBUG",
                "file": str(tmp_path / "test.log"),
            },
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as fh:
            yaml.dump(cfg, fh)

        # Patch time.sleep so tests run instantly
        with patch("src.main.time.sleep"):
            run(str(config_path))

        out = tmp_path / "output"
        assert (out / "MOCK_historical.csv").exists()
        assert (out / "MOCK_summary.txt").exists()