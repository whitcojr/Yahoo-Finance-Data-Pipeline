# 📈 Yahoo Finance Data Pipeline

![Tests](https://github.com/<whitcojr>/Yahoo-Finance-Data-Pipeline/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A configurable Python pipeline that pulls stock data from Yahoo Finance,
calculates derived metrics, and exports clean reports — all driven by a
single YAML config file.

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

```bash
git clone https://github.com/<your-username>/Yahoo-Finance-Data-Pipeline.git
cd Yahoo-Finance-Data-Pipeline

python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
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