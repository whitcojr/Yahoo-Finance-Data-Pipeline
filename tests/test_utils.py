"""
test_utils.py – Unit tests for src/utils.py

These tests use only synthetic data so they run offline and fast.
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.utils import (
    add_derived_metrics,
    clean_historical_data,
    ensure_output_dir,
    export_dataframe,
    extract_key_metrics,
    generate_summary_report,
    load_config,
    setup_logging,
)


# ────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────

@pytest.fixture
def sample_config(tmp_path):
    """Write a minimal config.yaml and return its path."""
    cfg = {
        "tickers": ["AAPL", "MSFT"],
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
        "moving_averages": [5, 10],
        "output": {"directory": str(tmp_path / "output"), "format": "csv", "summary_report": True},
        "logging": {"level": "DEBUG", "file": str(tmp_path / "test.log")},
    }
    path = tmp_path / "config.yaml"
    with open(path, "w") as fh:
        yaml.dump(cfg, fh)
    return str(path)


@pytest.fixture
def sample_ohlcv():
    """Return a small synthetic OHLCV DataFrame."""
    dates = pd.date_range("2024-01-02", periods=30, freq="B")
    np.random.seed(42)
    close = 150 + np.cumsum(np.random.randn(30)).round(2)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.random.randint(1_000_000, 5_000_000, size=30),
        },
        index=dates,
    )


@pytest.fixture
def sample_info():
    """Return a dict mimicking yfinance Ticker.info."""
    return {
        "shortName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3_000_000_000_000,
        "trailingPE": 29.5,
        "forwardPE": 27.1,
        "trailingEps": 6.42,
        "dividendYield": 0.005,
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 164.08,
        "averageVolume": 55_000_000,
        "beta": 1.24,
    }


# ────────────────────────────────────────────
# Config tests
# ────────────────────────────────────────────

class TestLoadConfig:
    def test_loads_valid_config(self, sample_config):
        cfg = load_config(sample_config)
        assert cfg["tickers"] == ["AAPL", "MSFT"]
        assert cfg["start_date"] == "2024-01-01"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_missing_key_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        with open(bad, "w") as fh:
            yaml.dump({"tickers": ["X"]}, fh)  # missing start_date
        with pytest.raises(ValueError, match="start_date"):
            load_config(str(bad))

    def test_empty_tickers_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        with open(bad, "w") as fh:
            yaml.dump({"tickers": [], "start_date": "2024-01-01", "end_date": "2024-06-30"}, fh)
        with pytest.raises(ValueError, match="empty"):
            load_config(str(bad))


# ────────────────────────────────────────────
# Logging tests
# ────────────────────────────────────────────

class TestSetupLogging:
    def test_logger_created(self, sample_config):
        cfg = load_config(sample_config)
        logger = setup_logging(cfg)
        assert logger.name == "finance_app"
        assert len(logger.handlers) >= 2  # file + console


# ────────────────────────────────────────────
# Data processing tests
# ────────────────────────────────────────────

class TestCleanHistoricalData:
    def test_basic_clean(self, sample_ohlcv):
        result = clean_historical_data(sample_ohlcv)
        assert not result.empty
        assert result["Close"].dtype == float

    def test_empty_df_returns_empty(self):
        result = clean_historical_data(pd.DataFrame())
        assert result.empty

    def test_fills_small_gaps(self, sample_ohlcv):
        df = sample_ohlcv.copy()
        df.iloc[5] = np.nan  # introduce a gap
        result = clean_historical_data(df)
        assert result.isna().sum().sum() == 0


class TestAddDerivedMetrics:
    def test_adds_pct_change(self, sample_ohlcv):
        result = add_derived_metrics(sample_ohlcv, windows=[5])
        assert "Daily_Pct_Change" in result.columns

    def test_adds_sma_columns(self, sample_ohlcv):
        result = add_derived_metrics(sample_ohlcv, windows=[5, 10])
        assert "SMA_5" in result.columns
        assert "SMA_10" in result.columns

    def test_empty_df(self):
        result = add_derived_metrics(pd.DataFrame(), windows=[5])
        assert result.empty

    def test_default_windows(self, sample_ohlcv):
        result = add_derived_metrics(sample_ohlcv)
        assert "SMA_20" in result.columns
        assert "SMA_50" in result.columns


# ────────────────────────────────────────────
# Metrics extraction tests
# ────────────────────────────────────────────

class TestExtractKeyMetrics:
    def test_extracts_all_fields(self, sample_info):
        metrics = extract_key_metrics(sample_info)
        assert metrics["Name"] == "Apple Inc."
        assert metrics["Market Cap"] == 3_000_000_000_000
        assert metrics["P/E Ratio (Trailing)"] == 29.5

    def test_missing_fields_default_na(self):
        metrics = extract_key_metrics({})
        assert metrics["Name"] == "N/A"
        assert metrics["P/E Ratio (Trailing)"] == "N/A"

    def test_none_values_default_na(self):
        info = {"shortName": None, "trailingPE": None}
        metrics = extract_key_metrics(info)
        assert metrics["Name"] == "N/A"


# ────────────────────────────────────────────
# Export tests
# ────────────────────────────────────────────

class TestExportDataframe:
    def test_csv_export(self, sample_ohlcv, tmp_path):
        export_dataframe(sample_ohlcv, tmp_path / "test", fmt="csv")
        assert (tmp_path / "test.csv").exists()

    def test_json_export(self, sample_ohlcv, tmp_path):
        export_dataframe(sample_ohlcv, tmp_path / "test", fmt="json")
        assert (tmp_path / "test.json").exists()

    def test_excel_export(self, sample_ohlcv, tmp_path):
        export_dataframe(sample_ohlcv, tmp_path / "test", fmt="excel")
        assert (tmp_path / "test.xlsx").exists()

    def test_invalid_format_raises(self, sample_ohlcv, tmp_path):
        with pytest.raises(ValueError, match="Unsupported"):
            export_dataframe(sample_ohlcv, tmp_path / "test", fmt="parquet")


# ────────────────────────────────────────────
# Summary report tests
# ────────────────────────────────────────────

class TestGenerateSummaryReport:
    def test_report_created(self, sample_ohlcv, sample_info, tmp_path):
        metrics = extract_key_metrics(sample_info)
        generate_summary_report("AAPL", metrics, sample_ohlcv, pd.DataFrame(), tmp_path)
        report = tmp_path / "AAPL_summary.txt"
        assert report.exists()
        content = report.read_text()
        assert "AAPL" in content
        assert "KEY METRICS" in content

    def test_report_with_empty_data(self, tmp_path):
        generate_summary_report("XYZ", {}, pd.DataFrame(), pd.DataFrame(), tmp_path)
        assert (tmp_path / "XYZ_summary.txt").exists()