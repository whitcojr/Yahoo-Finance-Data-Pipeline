"""
utils.py – Helper functions for configuration, logging, data processing,
           analysis (technical indicators, risk metrics, pairs trading,
           forecasting), and report generation.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

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

    df.ffill(inplace=True)
    df.bfill(inplace=True)
    df.dropna(how="all", inplace=True)

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
    """Add all derived technical indicators and risk metrics to a price DataFrame.

    Includes:
    - Daily return & log return
    - Simple moving averages (SMA) and exponential moving averages (EMA)
    - MACD + Signal line + Histogram
    - RSI (14-period)
    - Bollinger Bands (20-period, ±2σ)
    - Rolling 30-day annualised volatility
    - Cumulative return

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned OHLCV DataFrame (must contain a ``Close`` column).
    windows : list[int] or None
        Rolling-window sizes for SMAs. Defaults to ``[20, 50, 200]``.

    Returns
    -------
    pd.DataFrame
        DataFrame with new indicator columns appended.
    """
    if df.empty or "Close" not in df.columns:
        return df

    df = df.copy()
    windows = windows or [20, 50, 200]

    # ── Returns ──────────────────────────────
    df["Daily_Pct_Change"] = (df["Close"].pct_change() * 100).round(4)
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1)).round(6)

    # ── Moving averages ───────────────────────
    for w in windows:
        df[f"SMA_{w}"] = df["Close"].rolling(window=w).mean().round(2)

    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean().round(2)
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean().round(2)

    # ── MACD ──────────────────────────────────
    df["MACD"] = (df["EMA_12"] - df["EMA_26"]).round(4)
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean().round(4)
    df["MACD_Hist"] = (df["MACD"] - df["MACD_Signal"]).round(4)

    # ── RSI (14) ──────────────────────────────
    df["RSI_14"] = _compute_rsi(df["Close"], period=14).round(2)

    # ── Bollinger Bands (20, ±2σ) ─────────────
    bb_mid = df["Close"].rolling(20).mean()
    bb_std = df["Close"].rolling(20).std()
    df["BB_Upper"] = (bb_mid + 2 * bb_std).round(2)
    df["BB_Mid"]   = bb_mid.round(2)
    df["BB_Lower"] = (bb_mid - 2 * bb_std).round(2)
    df["BB_Width"] = ((df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"]).round(4)

    # ── Volatility ────────────────────────────
    daily_ret = df["Close"].pct_change()
    df["Volatility_30d"] = (daily_ret.rolling(30).std() * np.sqrt(252) * 100).round(4)

    # ── Cumulative return ─────────────────────
    df["Cumulative_Return"] = ((df["Close"] / df["Close"].iloc[0]) - 1).round(6)

    return df


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed RSI.

    Parameters
    ----------
    series : pd.Series
        Closing price series.
    period : int
        Look-back window (default 14).

    Returns
    -------
    pd.Series
    """
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


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
# Risk analytics
# ────────────────────────────────────────────

def compute_risk_metrics(df: pd.DataFrame, risk_free_rate: float = 0.0) -> Dict[str, Any]:
    """Compute portfolio-level risk and return statistics for a single ticker.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame that has already been processed by ``add_derived_metrics``.
        Must contain ``Close`` and ``Daily_Pct_Change`` columns.
    risk_free_rate : float
        Annualised risk-free rate as a decimal (e.g. ``0.05`` for 5 %).
        Defaults to 0.

    Returns
    -------
    dict
        Dictionary of labelled risk metrics.
    """
    if df.empty or "Close" not in df.columns:
        return {}

    daily_ret = df["Close"].pct_change().dropna()
    annual_factor = 252

    total_return = (df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1
    ann_vol = daily_ret.std() * np.sqrt(annual_factor)
    daily_rf = (1 + risk_free_rate) ** (1 / annual_factor) - 1
    excess = daily_ret - daily_rf
    sharpe = (excess.mean() / excess.std()) * np.sqrt(annual_factor) if excess.std() != 0 else np.nan

    # Sortino (downside deviation only)
    downside = daily_ret[daily_ret < daily_rf]
    sortino = (excess.mean() / downside.std()) * np.sqrt(annual_factor) if len(downside) > 1 else np.nan

    # Max drawdown
    rolling_max = df["Close"].cummax()
    drawdown = (df["Close"] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    # Value at Risk (historical, 95 % confidence)
    var_95 = np.percentile(daily_ret, 5)

    # Conditional VaR / Expected Shortfall
    cvar_95 = daily_ret[daily_ret <= var_95].mean()

    return {
        "Total Return": round(total_return, 6),
        "Annualised Volatility": round(ann_vol, 6),
        "Sharpe Ratio": round(sharpe, 4) if not np.isnan(sharpe) else "N/A",
        "Sortino Ratio": round(sortino, 4) if not np.isnan(sortino) else "N/A",
        "Max Drawdown": round(max_drawdown, 6),
        "VaR 95% (1-day)": round(var_95, 6),
        "CVaR 95% (1-day)": round(cvar_95, 6),
        "Skewness": round(float(daily_ret.skew()), 4),
        "Kurtosis": round(float(daily_ret.kurtosis()), 4),
    }


# ────────────────────────────────────────────
# Multi-ticker analysis
# ────────────────────────────────────────────

def build_close_matrix(ticker_dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Stack per-ticker Close series into a single aligned DataFrame.

    Parameters
    ----------
    ticker_dfs : dict[str, pd.DataFrame]
        Mapping of ticker symbol → processed historical DataFrame.
        Each DataFrame must have a DatetimeIndex or a ``Date`` column.

    Returns
    -------
    pd.DataFrame
        Wide DataFrame with dates as index and tickers as columns.
        Rows with any NaN are dropped.
    """
    closes: Dict[str, pd.Series] = {}
    for ticker, df in ticker_dfs.items():
        if df.empty or "Close" not in df.columns:
            continue
        tmp = df.copy()
        if "Date" in tmp.columns:
            tmp = tmp.set_index("Date")
        closes[ticker] = tmp["Close"]

    if not closes:
        return pd.DataFrame()

    return pd.DataFrame(closes).dropna()


def compute_correlation_matrix(close_matrix: pd.DataFrame) -> pd.DataFrame:
    """Return the Pearson correlation matrix of daily returns.

    Parameters
    ----------
    close_matrix : pd.DataFrame
        Wide price DataFrame from ``build_close_matrix``.

    Returns
    -------
    pd.DataFrame
        Correlation matrix (tickers × tickers).
    """
    if close_matrix.empty:
        return pd.DataFrame()
    return close_matrix.pct_change().dropna().corr().round(4)


def compute_pairs_spread(
    close_matrix: pd.DataFrame,
    ticker_a: str,
    ticker_b: str,
) -> pd.DataFrame:
    """Compute the hedge-ratio-adjusted spread and z-score for a ticker pair.

    The hedge ratio is calculated as the mean-price ratio so that both legs
    are expressed in comparable dollar terms.  A z-score beyond ±2 is a
    conventional signal threshold for mean-reversion pairs trades.

    Parameters
    ----------
    close_matrix : pd.DataFrame
        Wide price DataFrame from ``build_close_matrix``.
    ticker_a : str
    ticker_b : str

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ``Spread``, ``Z_Score``, ``Signal``
        (``"buy"``, ``"sell"``, or ``""``).

    Raises
    ------
    KeyError
        If either ticker is not present in ``close_matrix``.
    """
    for t in (ticker_a, ticker_b):
        if t not in close_matrix.columns:
            raise KeyError(f"Ticker '{t}' not found in close matrix")

    hedge_ratio = close_matrix[ticker_a].mean() / close_matrix[ticker_b].mean()
    spread = close_matrix[ticker_a] - hedge_ratio * close_matrix[ticker_b]
    z = (spread - spread.mean()) / spread.std()

    result = pd.DataFrame({
        "Spread": spread.round(4),
        "Z_Score": z.round(4),
    }, index=close_matrix.index)

    result["Signal"] = ""
    result.loc[result["Z_Score"] < -2, "Signal"] = "buy"
    result.loc[result["Z_Score"] >  2, "Signal"] = "sell"

    return result


# ────────────────────────────────────────────
# Forecasting
# ────────────────────────────────────────────

def forecast_with_prophet(
    df: pd.DataFrame,
    periods: int = 90,
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = True,
) -> Tuple[pd.DataFrame, Any]:
    """Fit a Facebook Prophet model and return future predictions.

    Parameters
    ----------
    df : pd.DataFrame
        Processed historical DataFrame. Must contain ``Date`` and ``Close``
        columns.
    periods : int
        Number of calendar days to forecast beyond the last observed date.
    yearly_seasonality : bool
    weekly_seasonality : bool

    Returns
    -------
    tuple[pd.DataFrame, prophet.Prophet]
        ``(forecast_df, fitted_model)``

        ``forecast_df`` contains Prophet's standard output columns including
        ``ds``, ``yhat``, ``yhat_lower``, ``yhat_upper``.

    Raises
    ------
    ImportError
        If ``prophet`` is not installed.
    ValueError
        If the DataFrame is too short to fit a model.
    """
    try:
        from prophet import Prophet  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Prophet is not installed. Run: pip install prophet"
        ) from exc

    if df.empty or "Close" not in df.columns:
        raise ValueError("DataFrame must contain a 'Close' column with data")

    if len(df) < 30:
        raise ValueError("At least 30 rows of data are required to fit Prophet")

    tmp = df[["Date", "Close"]].copy()
    tmp.columns = ["ds", "y"]
    tmp["ds"] = pd.to_datetime(tmp["ds"])

    model = Prophet(
        daily_seasonality=False,
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        uncertainty_samples=200,
    )
    model.fit(tmp)

    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)

    return forecast, model


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


# ────────────────────────────────────────────
# Report generation
# ────────────────────────────────────────────

def generate_summary_report(
    ticker: str,
    metrics: Dict[str, Any],
    hist_df: pd.DataFrame,
    earnings_df: pd.DataFrame,
    output_dir: Path,
    risk_metrics: Optional[Dict[str, Any]] = None,
    pairs_results: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> None:
    """Write a plain-text summary report for a single ticker.

    Parameters
    ----------
    ticker : str
    metrics : dict
        Key financial metrics from ``extract_key_metrics``.
    hist_df : pd.DataFrame
        Processed historical price data.
    earnings_df : pd.DataFrame
        Quarterly earnings from ``extract_earnings``.
    output_dir : pathlib.Path
    risk_metrics : dict or None
        Output of ``compute_risk_metrics``.
    pairs_results : dict or None
        Mapping of ``(ticker_a, ticker_b)`` → spread DataFrame from
        ``compute_pairs_spread``.  Any pairs involving this ticker are
        included in the report.
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

    # ── Price statistics ──────────────────────
    if not hist_df.empty and "Close" in hist_df.columns:
        lines += [
            "",
            "PRICE STATISTICS",
            "-" * 40,
            f"  Period high:      ${hist_df['Close'].max():,.2f}",
            f"  Period low:       ${hist_df['Close'].min():,.2f}",
            f"  Period mean:      ${hist_df['Close'].mean():,.2f}",
            f"  Total return:     {((hist_df['Close'].iloc[-1] / hist_df['Close'].iloc[0]) - 1) * 100:,.2f}%",
        ]

        # Latest indicator snapshot
        last = hist_df.iloc[-1]
        indicator_rows = []
        for col, label in [
            ("RSI_14",        "RSI (14)"),
            ("MACD",          "MACD"),
            ("MACD_Signal",   "MACD Signal"),
            ("BB_Upper",      "Bollinger Upper"),
            ("BB_Lower",      "Bollinger Lower"),
            ("Volatility_30d","30d Ann. Volatility (%)"),
        ]:
            if col in hist_df.columns and pd.notna(last.get(col)):
                indicator_rows.append(f"  {label:<30} {last[col]:,.4f}")

        if indicator_rows:
            lines += ["", "LATEST TECHNICAL INDICATORS", "-" * 40]
            lines += indicator_rows

            # RSI signal hint
            if "RSI_14" in hist_df.columns and pd.notna(last.get("RSI_14")):
                rsi_val = last["RSI_14"]
                if rsi_val > 70:
                    lines.append("  ⚠  RSI > 70: potentially overbought")
                elif rsi_val < 30:
                    lines.append("  ⚠  RSI < 30: potentially oversold")

            # MACD signal hint
            if "MACD_Hist" in hist_df.columns and len(hist_df) >= 2:
                prev_hist = hist_df["MACD_Hist"].iloc[-2]
                curr_hist = hist_df["MACD_Hist"].iloc[-1]
                if prev_hist < 0 and curr_hist >= 0:
                    lines.append("  ✔  MACD histogram crossed above zero (bullish)")
                elif prev_hist > 0 and curr_hist <= 0:
                    lines.append("  ✔  MACD histogram crossed below zero (bearish)")

    # ── Risk metrics ──────────────────────────
    if risk_metrics:
        lines += ["", "RISK & RETURN METRICS", "-" * 40]
        for k, v in risk_metrics.items():
            if isinstance(v, float):
                v = f"{v:,.4f}"
            lines.append(f"  {k:<30} {v}")

    # ── Pairs trading ─────────────────────────
    if pairs_results:
        relevant = {
            pair: spread_df
            for pair, spread_df in pairs_results.items()
            if ticker in pair
        }
        if relevant:
            lines += ["", "PAIRS TRADING SIGNALS", "-" * 40]
            for (ta, tb), spread_df in relevant.items():
                last_z = spread_df["Z_Score"].iloc[-1]
                last_sig = spread_df["Signal"].iloc[-1]
                buy_count  = (spread_df["Signal"] == "buy").sum()
                sell_count = (spread_df["Signal"] == "sell").sum()
                lines += [
                    f"  Pair: {ta} / {tb}",
                    f"    Current Z-Score:  {last_z:,.4f}",
                    f"    Current Signal:   {last_sig if last_sig else 'neutral'}",
                    f"    Buy signals (z<-2):  {buy_count}",
                    f"    Sell signals (z>2):  {sell_count}",
                ]

    # ── Earnings ──────────────────────────────
    if not earnings_df.empty:
        lines += ["", "RECENT QUARTERLY EARNINGS / REVENUE", "-" * 40]
        lines.append(earnings_df.to_string())

    report_path = output_dir / f"{ticker}_summary.txt"
    with open(report_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")