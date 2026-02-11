"""
utils.py – Helper functions for configuration, logging, data processing,
           and report generation.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml


# ────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Load and validate the YAML configuration file.

    Parameters
    ----------
    path : str
        Path to the YAML config file (default ``config.yaml``).

    Returns
    -------
    dict
        Parsed configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    ValueError
        If required keys are missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r") as fh:
        config = yaml.safe_load(fh)

    # Basic validation
    required_keys = ["tickers", "start_date", "end_date"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: '{key}'")

    if not config["tickers"]:
        raise ValueError("Ticker list must not be empty")

    return config


# ────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────

def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configure and return the application logger.

    Logs go to both a file and stderr so CI pipelines can capture output.

    Parameters
    ----------
    config : dict
        Application configuration (uses ``config["logging"]``).

    Returns
    -------
    logging.Logger
    """
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = log_cfg.get("file", "app.log")

    logger = logging.getLogger("finance_app")
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


# ────────────────────────────────────────────
# Data processing helpers
# ────────────────────────────────────────────

def clean_historical_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw historical price data from yfinance.

    * Forward-fills then back-fills small gaps (weekends/holidays already
      excluded by yfinance, but this covers splits/data glitches).
    * Drops any rows that are still entirely NaN after filling.
    * Rounds prices to 2 decimal places and volume to int.

    Parameters
    ----------
    df : pd.DataFrame
        Raw OHLCV DataFrame from ``yf.Ticker.history()``.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame.
    """
    if df.empty:
        return df

    df = df.copy()

    # Forward-fill then back-fill small gaps
    df.ffill(inplace=True)
    df.bfill(inplace=True)

    # Drop rows that are completely empty
    df.dropna(how="all", inplace=True)

    # Round numeric columns
    price_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
    for col in price_cols:
        df[col] = df[col].round(2)
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].astype(int, errors="ignore")

    return df


def add_derived_metrics(
    df: pd.DataFrame,
    windows: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Add moving averages and daily percentage change.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned OHLCV DataFrame (must contain a ``Close`` column).
    windows : list[int] or None
        Rolling-window sizes for simple moving averages. Defaults to
        ``[20, 50]``.

    Returns
    -------
    pd.DataFrame
        DataFrame with new columns added.
    """
    if df.empty or "Close" not in df.columns:
        return df

    df = df.copy()
    windows = windows or [20, 50]

    # Daily percentage change
    df["Daily_Pct_Change"] = df["Close"].pct_change() * 100
    df["Daily_Pct_Change"] = df["Daily_Pct_Change"].round(4)

    # Simple moving averages
    for w in windows:
        col_name = f"SMA_{w}"
        df[col_name] = df["Close"].rolling(window=w).mean().round(2)

    return df


def extract_key_metrics(info: Dict[str, Any]) -> Dict[str, Any]:
    """Pull key financial metrics from the yfinance ``info`` dict.

    Parameters
    ----------
    info : dict
        Result of ``yf.Ticker(...).info``.

    Returns
    -------
    dict
        Curated metrics with human-friendly keys.
    """
    def _get(key: str, fallback: Any = "N/A") -> Any:
        val = info.get(key, fallback)
        return val if val is not None else fallback

    return {
        "Name": _get("shortName"),
        "Sector": _get("sector"),
        "Industry": _get("industry"),
        "Market Cap": _get("marketCap"),
        "P/E Ratio (Trailing)": _get("trailingPE"),
        "P/E Ratio (Forward)": _get("forwardPE"),
        "EPS (Trailing)": _get("trailingEps"),
        "Dividend Yield": _get("dividendYield"),
        "52-Week High": _get("fiftyTwoWeekHigh"),
        "52-Week Low": _get("fiftyTwoWeekLow"),
        "Average Volume": _get("averageVolume"),
        "Beta": _get("beta"),
    }


def extract_earnings(ticker_obj) -> pd.DataFrame:
    """Extract quarterly earnings data from a yfinance Ticker.

    Parameters
    ----------
    ticker_obj : yfinance.Ticker

    Returns
    -------
    pd.DataFrame
        Earnings/revenue data with columns ``Revenue`` and ``Earnings``.
    """
    try:
        earnings = ticker_obj.quarterly_financials
        if earnings is not None and not earnings.empty:
            rows = {}
            if "Total Revenue" in earnings.index:
                rows["Revenue"] = earnings.loc["Total Revenue"]
            if "Net Income" in earnings.index:
                rows["Earnings"] = earnings.loc["Net Income"]
            if rows:
                return pd.DataFrame(rows)
    except Exception:
        pass
    return pd.DataFrame()


# ────────────────────────────────────────────
# Export helpers
# ────────────────────────────────────────────

def ensure_output_dir(config: Dict[str, Any]) -> Path:
    """Create (if needed) and return the output directory path."""
    out_dir = Path(config.get("output", {}).get("directory", "output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def export_dataframe(
    df: pd.DataFrame,
    filepath: Path,
    fmt: str = "csv",
) -> None:
    """Export a DataFrame to the chosen format.

    Parameters
    ----------
    df : pd.DataFrame
    filepath : pathlib.Path
        Destination path **without** extension (extension added automatically).
    fmt : str
        One of ``csv``, ``excel``, ``json``.
    """
    if fmt == "csv":
        target = filepath.with_suffix(".csv")
        df.to_csv(target)
    elif fmt == "excel":
        target = filepath.with_suffix(".xlsx")
        df.to_excel(target, engine="openpyxl")
    elif fmt == "json":
        target = filepath.with_suffix(".json")
        df.to_json(target, orient="records", date_format="iso", indent=2)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")


def generate_summary_report(
    ticker: str,
    metrics: Dict[str, Any],
    hist_df: pd.DataFrame,
    earnings_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Write a plain-text summary report for a single ticker.

    Parameters
    ----------
    ticker : str
    metrics : dict
    hist_df : pd.DataFrame
    earnings_df : pd.DataFrame
    output_dir : pathlib.Path
    """
    lines = [
        f"{'=' * 60}",
        f"  Financial Summary Report – {ticker}",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"{'=' * 60}",
        "",
        "KEY METRICS",
        "-" * 40,
    ]

    for k, v in metrics.items():
        if isinstance(v, float):
            v = f"{v:,.2f}"
        elif isinstance(v, int):
            v = f"{v:,}"
        lines.append(f"  {k:<30} {v}")

    if not hist_df.empty and "Close" in hist_df.columns:
        lines += [
            "",
            "PRICE STATISTICS",
            "-" * 40,
            f"  Period high:   ${hist_df['Close'].max():,.2f}",
            f"  Period low:    ${hist_df['Close'].min():,.2f}",
            f"  Period mean:   ${hist_df['Close'].mean():,.2f}",
            f"  Total return:  {((hist_df['Close'].iloc[-1] / hist_df['Close'].iloc[0]) - 1) * 100:,.2f}%",
        ]

    if not earnings_df.empty:
        lines += ["", "RECENT QUARTERLY EARNINGS / REVENUE", "-" * 40]
        lines.append(earnings_df.to_string())

    report_path = output_dir / f"{ticker}_summary.txt"
    with open(report_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")