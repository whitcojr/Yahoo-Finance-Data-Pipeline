"""
main.py – Entry point for the Yahoo Finance data pipeline.

Usage
-----
    python -m src.main                   # uses default config.yaml
    python -m src.main --config my.yaml  # custom config path

Design decisions
----------------
* **yfinance** is used instead of the (retired) official Yahoo Finance API.
  yfinance is the most popular open-source wrapper, is actively maintained,
  and provides a clean Pythonic interface for prices, fundamentals, and
  earnings data — all without an API key.
* Data is fetched ticker-by-ticker with a small delay (``time.sleep``) to
  be a polite client and avoid transient 429s.
* All processing lives in ``utils.py`` so it can be unit-tested in isolation.
"""

import argparse
import sys
import time
from pathlib import Path

import yfinance as yf

from src.utils import (
    add_derived_metrics,
    clean_historical_data,
    ensure_output_dir,
    export_dataframe,
    extract_earnings,
    extract_key_metrics,
    generate_summary_report,
    load_config,
    setup_logging,
)


def fetch_ticker_data(
    symbol: str,
    start: str,
    end: str,
    ma_windows: list,
    logger,
):
    """Fetch and process all data for a single ticker.

    Parameters
    ----------
    symbol : str
        Stock ticker (e.g. ``"AAPL"``).
    start, end : str
        ISO date strings for the historical window.
    ma_windows : list[int]
        Moving-average window sizes.
    logger : logging.Logger

    Returns
    -------
    dict
        Keys: ``"historical"``, ``"metrics"``, ``"earnings"`` — each
        holding the processed data (DataFrame or dict).
    """
    logger.info(f"Fetching data for {symbol} …")
    ticker = yf.Ticker(symbol)

    # 1. Historical prices ------------------------------------------------
    try:
        hist = ticker.history(start=start, end=end, auto_adjust=True)
        if hist.empty:
            logger.warning(f"No historical data returned for {symbol}")
        else:
            hist = clean_historical_data(hist)
            hist = add_derived_metrics(hist, windows=ma_windows)
            logger.info(f"  {symbol}: {len(hist)} trading days retrieved")
    except Exception as exc:
        logger.error(f"  Historical data error for {symbol}: {exc}")
        hist = None

    # 2. Key metrics ------------------------------------------------------
    try:
        info = ticker.info or {}
        metrics = extract_key_metrics(info)
        logger.info(f"  {symbol}: key metrics extracted")
    except Exception as exc:
        logger.error(f"  Metrics error for {symbol}: {exc}")
        metrics = {}

    # 3. Earnings / revenue -----------------------------------------------
    try:
        earnings = extract_earnings(ticker)
        if earnings.empty:
            logger.info(f"  {symbol}: no earnings data available")
        else:
            logger.info(f"  {symbol}: earnings data extracted")
    except Exception as exc:
        logger.error(f"  Earnings error for {symbol}: {exc}")
        earnings = None

    return {
        "historical": hist,
        "metrics": metrics,
        "earnings": earnings,
    }


def run(config_path: str = "config.yaml") -> None:
    """Main pipeline: load config → fetch → process → export.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file.
    """
    # ── Setup ────────────────────────────────
    config = load_config(config_path)
    logger = setup_logging(config)
    logger.info("Configuration loaded successfully")

    tickers = config["tickers"]
    start = config["start_date"]
    end = config["end_date"]
    ma_windows = config.get("moving_averages", [20, 50])
    out_fmt = config.get("output", {}).get("format", "csv")
    gen_summary = config.get("output", {}).get("summary_report", True)
    out_dir = ensure_output_dir(config)

    logger.info(f"Tickers : {tickers}")
    logger.info(f"Window  : {start}  →  {end}")
    logger.info(f"Output  : {out_dir}/  ({out_fmt})")

    # ── Fetch & process each ticker ──────────
    all_results = {}
    for symbol in tickers:
        result = fetch_ticker_data(symbol, start, end, ma_windows, logger)
        all_results[symbol] = result

        # Polite delay between tickers
        time.sleep(0.5)

    # ── Export ────────────────────────────────
    for symbol, data in all_results.items():
        hist = data["historical"]
        metrics = data["metrics"]
        earnings = data["earnings"]

        # Historical prices
        if hist is not None and not hist.empty:
            export_dataframe(hist, out_dir / f"{symbol}_historical", fmt=out_fmt)
            logger.info(f"Exported {symbol} historical data")

        # Earnings
        if earnings is not None and not earnings.empty:
            export_dataframe(earnings, out_dir / f"{symbol}_earnings", fmt=out_fmt)
            logger.info(f"Exported {symbol} earnings data")

        # Summary report
        if gen_summary:
            generate_summary_report(
                symbol,
                metrics,
                hist if hist is not None else __import__("pandas").DataFrame(),
                earnings if earnings is not None else __import__("pandas").DataFrame(),
                out_dir,
            )
            logger.info(f"Generated summary report for {symbol}")

    logger.info("Pipeline complete ✓")


# ────────────────────────────────────────────
# CLI entry point
# ────────────────────────────────────────────

def main() -> None:
    """Parse CLI args and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="Pull financial data from Yahoo Finance"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()