# Yahoo Finance Data Pipeline

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

This project pulls market data from Yahoo Finance, calculates technical and risk metrics, exports files for offline analysis, and includes a Streamlit dashboard for interactive exploration.

It supports two workflows:

1. A CLI pipeline that fetches ticker data and writes output files.
2. A Streamlit app that visualizes price action, comparisons, risk analytics, and forecasts.

## What The Dashboard Shows

The Streamlit dashboard is designed to answer a practical question quickly: what has this ticker been doing, how risky has it been, how does it compare to other names, and what does a simple forecast imply.

### KPI Row

At the top of the dashboard, users see a compact summary of the selected ticker:

- Current Price: latest adjusted close with daily percentage change.
- Market Cap: company size, when Yahoo Finance provides it.
- P/E Ratio: trailing price-to-earnings ratio.
- 52W High: the highest price reached over the last 52 weeks.
- Annual Volatility: annualized standard deviation of daily returns.

These metrics provide a fast snapshot of price level, valuation, scale, and risk.

### Price Action

The main chart section focuses on how price is moving over time.

- Candlestick chart: shows daily open, high, low, and close.
- Moving Averages: overlays 20-day, 50-day, and 200-day simple moving averages to show short-, medium-, and long-term trend direction.
- Bollinger Bands: shows a volatility envelope around price using a 20-day average and rolling standard deviation.
- Volume: plots trading activity beneath the price chart.
- MACD: plots momentum using the difference between the 12-day and 26-day exponential moving averages, plus the MACD signal line and histogram.
- RSI (14): measures recent price strength on a 0 to 100 scale to highlight overbought or oversold conditions.

In plain English:

- Moving averages help users see whether price is trending up or down.
- Bollinger Bands help users see when price is unusually stretched relative to recent behavior.
- MACD helps users spot momentum shifts.
- RSI helps users judge whether a move may be overheated or washed out.

### Multi-Ticker Comparison

When multiple tickers are entered, the dashboard adds a comparison section with three views.

- Normalized Returns: rebases each ticker to 100 so users can compare relative performance rather than raw price.
- Correlation Heatmap: shows how similarly the selected tickers move on a day-to-day basis.
- Pairs Spread: compares two tickers using a simple hedge ratio and plots the spread plus z-score.

Why this matters:

- Normalized returns show which asset outperformed over the same period.
- Correlation shows whether names tend to move together or independently.
- Pairs spread helps users see whether two assets have diverged unusually far from their recent relationship.

### Risk And Return Analytics

This section summarizes how volatile and asymmetric the selected ticker has been.

- Return Distribution: histogram of daily returns.
- VaR 95%: estimated one-day value at risk based on the 5th percentile of historical daily returns.
- 30-Day Rolling Volatility: rolling annualized volatility over time.
- Risk Table: Total Return, Annualized Volatility, Sharpe Ratio, Max Drawdown, VaR 95%, Skewness, and Kurtosis.

What these mean:

- Total Return: overall gain or loss across the selected period.
- Annualized Volatility: how much the price tends to move.
- Sharpe Ratio: return earned per unit of volatility, assuming a 0% risk-free rate.
- Max Drawdown: worst peak-to-trough decline during the period.
- Skewness: whether extreme upside or downside days are more common.
- Kurtosis: whether return tails are fatter than a normal distribution.

### Prophet Forecast

The dashboard can optionally train a Prophet model and produce a forward-looking price projection.

- Forecast Line: projected future path.
- Forecast Start Marker: where historical data ends and forecast begins.
- 95% Confidence Interval: upper and lower forecast bounds.
- Forecast Summary Metrics: current price, projected future price, and forecast range.

Important note: this is a statistical forecast, not investment advice. It is best used as a scenario tool rather than a prediction guarantee.

### Raw Data View

The dashboard also exposes the most recent processed rows and allows CSV download. This is useful when users want to inspect the underlying data behind the charts or export it for Excel, SQL, or additional analysis.

## Pipeline Outputs

The CLI pipeline exports one set of files per ticker.

| File | Description |
| --- | --- |
| `AAPL_historical.csv` | Historical OHLCV data plus derived indicators and return columns |
| `AAPL_earnings.csv` | Quarterly revenue and earnings data when available |
| `AAPL_summary.txt` | Plain-English summary report with key metrics and headline statistics |

Supported export formats are CSV, Excel, and JSON.

## Derived Metrics Calculated In The Pipeline

The data processing layer computes analytics that feed both exports and the dashboard.

- Daily return and log return
- Simple moving averages for configurable windows
- Exponential moving averages
- MACD, signal line, and histogram
- RSI (14)
- Bollinger Bands and band width
- 30-day rolling annualized volatility
- Cumulative return

## Project Structure

```text
Yahoo-Finance-Data-Pipeline/
|-- src/
|   |-- main.py
|   |-- utils.py
|   `-- config.yaml
|-- tests/
|   |-- test_main.py
|   `-- test_utils.py
|-- output/
|-- config.yaml
|-- streamlit_app.py
|-- requirements.txt
`-- README.md
```

## Setup

### 1. Clone The Repository

```bash
git clone https://github.com/whitcojr/Yahoo-Finance-Data-Pipeline.git
cd Yahoo-Finance-Data-Pipeline
```

### 2. Create And Activate A Virtual Environment

macOS or Linux:

```bash
python -m venv venv
source venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Windows Git Bash:

```bash
python -m venv venv
source venv/Scripts/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure The Tickers And Date Range

Edit `config.yaml`:

```yaml
tickers:
  - AAPL
  - MSFT
  - GOOGL

start_date: "2024-01-01"
end_date: "2024-12-31"

output:
  directory: "output"
  format: "csv"
  summary_report: true
```

## Run The CLI Pipeline

```bash
python -m src.main
python -m src.main --config my.yaml
```

Generated files are written to the configured output directory.

## Run The Streamlit Dashboard

```bash
streamlit run streamlit_app.py
```

From there, users can:

1. Enter one or more ticker symbols.
2. Change the analysis date range.
3. Toggle technical indicators on and off.
4. Compare multiple symbols.
5. Run the optional Prophet forecast.
6. Export the processed data as CSV.

## Testing

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Data Source

This project uses `yfinance`, which is a widely used open-source wrapper around Yahoo Finance data. It is convenient and free, but it depends on an unofficial upstream source, so occasional field changes or temporary rate limits can happen.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
# 📈 Yahoo Finance Data Pipeline

![Tests](https://github.com/<whitcojr>/Yahoo-Finance-Data-Pipeline/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A configurable Python pipeline that pulls stock data from Yahoo Finance,
calculates derived metrics, and exports clean reports — all driven by a
single YAML config file. I have found this very helpful to pull a company's data
and tranform it into a .csv file which can then be used in excel for 
financial evaluations or database work.

---

## Features

- **Historical prices** — daily OHLCV data for any date range
- **Key metrics** — P/E, market cap, dividend yield, beta, and more
- **Earnings data** — quarterly revenue and net income
- **Derived analytics** — simple moving averages, daily % change
- **Flexible export** — CSV, Excel, or JSON
- **Summary reports** — plain-text per-ticker reports
- **CI-ready** — GitHub Actions workflow with multi-version matrix

---

## Project Structure

```
Yahoo-Finance-Data-Pipeline/
├── .github/workflows/tests.yml   # CI pipeline
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point / orchestrator
│   ├── utils.py                   # Config, processing, export helpers
│   ├── config.yaml                # Tickers, dates, output prefs (copy)
│   ├── app.log                    # Pipeline execution logs
│   └── output/                    # Generated CSV/Excel/JSON files
├── tests/
│   ├── __init__.py
│   ├── test_main.py               # Integration tests (mocked API)
│   └── test_utils.py              # Unit tests (pure functions)
├── config.yaml                    # Tickers, dates, output prefs (main)
├── pytest.ini                     # Pytest configuration
├── .gitignore
├── AGENTS.md                      # AI usage documentation
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Quick Start

### 1. Clone & create a virtual environment

**macOS / Linux:**

```bash
git clone https://github.com/whitcojr/Yahoo-Finance-Data-Pipeline.git
cd Yahoo-Finance-Data-Pipeline
python -m venv venv
source venv/bin/activate
```

**Windows (Git Bash):**

```bash
git clone https://github.com/whitcojr/Yahoo-Finance-Data-Pipeline.git
cd Yahoo-Finance-Data-Pipeline
python -m venv venv
source venv/Scripts/activate
```


### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Edit **`config.yaml`** to set your tickers, date range, and output
preferences:

```yaml
tickers:
  - AAPL
  - MSFT
  - GOOGL

start_date: "2024-01-01"
end_date: "2024-12-31"

output:
  directory: "output"
  format: "csv"          # csv | excel | json
  summary_report: true
```

### 4. Run

```bash
python -m src.main                   # uses config.yaml (run from project root)
python -m src.main --config my.yaml  # custom config (run from project root)
```

Output files appear in the `src/output/` directory.

### 5. Run tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Output Files

After a successful run, you will find (per ticker):

| File                      | Contents                                    |
| ------------------------- | ------------------------------------------- |
| `AAPL_historical.csv`    | Daily OHLCV + SMA + % change               |
| `AAPL_earnings.csv`      | Quarterly revenue & earnings (if available) |
| `AAPL_summary.txt`       | Human-readable key metrics & statistics     |

---

## API Choice: yfinance vs. Alternatives

| Option               | Pros                                          | Cons                                  |
| -------------------- | --------------------------------------------- | ------------------------------------- |
| **yfinance** ✅      | Free, no API key, rich data, active community | Unofficial; Yahoo may rate-limit      |
| Alpha Vantage        | Official API key, reliable                    | Free tier = 25 calls/day              |
| Polygon.io           | Real-time data, WebSocket                     | Paid for most features                |
| Yahoo Finance v7 API | Direct REST                                   | Undocumented, frequently changes      |

**Recommendation:** `yfinance` is the best fit for this project — it's free,
requires no registration, and provides prices + fundamentals + earnings in
one library. The trade-off is that it scrapes Yahoo, so occasional breaking
changes are possible; the library's maintainers patch these quickly.

---

## License

[MIT](LICENSE)
