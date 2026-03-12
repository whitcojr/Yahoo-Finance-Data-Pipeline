"""
streamlit_app.py  —  Yahoo Finance Data Pipeline Dashboard
Drop this file in your project root and run:  streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
import yaml
from pathlib import Path
from datetime import datetime, timedelta

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0f1117; }
    [data-testid="stSidebar"] * {
        color: #f8fafc;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: #f8fafc;
    }
    /* Make user-entered values high contrast in input controls. */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background-color: #f8fafc;
        color: #0f1117;
        border: 1px solid #f8fafc;
        font-weight: 700;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #dbe4ee;
        color: #0f1117;
        border-color: #dbe4ee;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a1d2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 4px 0;
    }
    .metric-label { color: #8892b0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { color: #ccd6f6; font-size: 24px; font-weight: 700; margin-top: 4px; }
    .metric-delta-pos { color: #64ffda; font-size: 13px; }
    .metric-delta-neg { color: #ff6b6b; font-size: 13px; }
    .section-title {
        color: #64ffda;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 1px solid #0f3460;
        padding-bottom: 8px;
        margin: 24px 0 16px 0;
    }
    div[data-testid="metric-container"] {
        background: #1a1d2e;
        border: 1px solid #0f3460;
        border-radius: 10px;
        padding: 12px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────────
def load_config():
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {"tickers": ["AAPL", "MSFT", "GOOGL"], "start_date": "2023-01-01", "end_date": datetime.today().strftime("%Y-%m-%d")}


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def show_user_friendly_error(context: str, error: Exception) -> None:
    """Display plain-English guidance for end users and optional technical details."""
    if isinstance(error, (AttributeError, KeyError)):
        st.error(
            f"{context} could not complete because incoming data was missing a required field."
        )
        st.info(
            "How to fix it: try a different ticker, shorten the date range, or rerun in a minute. "
            "If the problem keeps happening, update dependencies with `pip install -U yfinance prophet pandas`."
        )
    elif isinstance(error, ValueError):
        st.error(f"{context} could not complete because one of the inputs is invalid.")
        st.info("How to fix it: check ticker symbols and date range, then run again.")
    else:
        st.error(f"{context} failed. Please try again.")

    with st.expander("Technical details"):
        st.code(f"{type(error).__name__}: {error}")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return df
    df = df.reset_index()
    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if col[1] == '' else col[0] for col in df.columns]
    df.columns = [str(c).strip() for c in df.columns]
    required_cols = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise AttributeError(f"Missing columns in downloaded data: {', '.join(sorted(missing))}")
    df["Daily_Return"] = df["Close"].pct_change()
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["SMA_200"] = df["Close"].rolling(200).mean()
    df["EMA_12"] = df["Close"].ewm(span=12).mean()
    df["EMA_26"] = df["Close"].ewm(span=26).mean()
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    df["RSI"] = compute_rsi(df["Close"])
    df["Volatility_30d"] = df["Daily_Return"].rolling(30).std() * np.sqrt(252)
    df["BB_Mid"] = df["SMA_20"]
    df["BB_Upper"] = df["BB_Mid"] + 2 * df["Close"].rolling(20).std()
    df["BB_Lower"] = df["BB_Mid"] - 2 * df["Close"].rolling(20).std()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_multi(tickers: list, start: str, end: str) -> pd.DataFrame:
    closes = {}
    for t in tickers:
        df = fetch_data(t, start, end)
        if not df.empty:
            closes[t] = df.set_index("Date")["Close"]
    return pd.DataFrame(closes).dropna()


# ── Sidebar ─────────────────────────────────────────────────────────────────────
config = load_config()

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    tickers_input = st.text_input(
        "Tickers (comma-separated)",
        value=", ".join(config.get("tickers", ["AAPL", "MSFT", "GOOGL"]))
    )
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start", value=pd.to_datetime(config.get("start_date", "2023-01-01")))
    with col2:
        end_date = st.date_input("End", value=pd.to_datetime(config.get("end_date", datetime.today().strftime("%Y-%m-%d"))))

    selected_ticker = st.selectbox("Primary Ticker", tickers)

    st.markdown("---")
    st.markdown("### 📐 Indicators")
    show_sma = st.checkbox("Moving Averages", value=True)
    show_bb = st.checkbox("Bollinger Bands", value=False)
    show_volume = st.checkbox("Volume", value=True)
    show_macd = st.checkbox("MACD", value=True)
    show_rsi = st.checkbox("RSI", value=True)

    st.markdown("---")
    st.markdown("### 🔮 Forecasting")
    forecast_days = st.slider("Forecast days (Prophet)", 30, 365, 90, step=30)
    run_forecast = st.button("Run Prophet Forecast", use_container_width=True)

    st.markdown("---")
    st.caption("Data via yfinance · Refreshes every 5 min")


start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")


# ── Main ─────────────────────────────────────────────────────────────────────────
st.markdown(f"# 📈 {selected_ticker} — Stock Analysis Dashboard")

with st.spinner(f"Fetching {selected_ticker}…"):
    try:
        df = fetch_data(selected_ticker, start_str, end_str)
        info = fetch_info(selected_ticker)
    except Exception as e:
        show_user_friendly_error("Data loading", e)
        st.stop()

if df.empty:
    st.error(f"No price data was found for {selected_ticker} in the selected date range.")
    st.info("How to fix it: confirm the ticker symbol, widen the date range, or try a different symbol.")
    st.stop()

if len(df) < 2:
    st.error(f"{selected_ticker} returned too little data to calculate changes and indicators.")
    st.info("How to fix it: extend the date range so at least a few trading days are available.")
    st.stop()

# ── KPI Row ───────────────────────────────────────────────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]
price_change = latest["Close"] - prev["Close"]
price_pct = price_change / prev["Close"] * 100

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Current Price", f"${latest['Close']:.2f}", f"{price_pct:+.2f}%")
with col2:
    st.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get("marketCap") else "—")
with col3:
    st.metric("P/E Ratio", f"{info.get('trailingPE', '—'):.1f}" if isinstance(info.get("trailingPE"), float) else "—")
with col4:
    st.metric("52W High", f"${info.get('fiftyTwoWeekHigh', 0):.2f}" if info.get("fiftyTwoWeekHigh") else "—")
with col5:
    annual_vol = df["Daily_Return"].std() * np.sqrt(252) * 100
    st.metric("Annual Volatility", f"{annual_vol:.1f}%")


# ── Price Chart ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Price Action</div>', unsafe_allow_html=True)

rows = 1 + show_volume + show_macd + show_rsi
row_heights = [0.5]
if show_volume: row_heights.append(0.15)
if show_macd:   row_heights.append(0.18)
if show_rsi:    row_heights.append(0.17)

subplot_titles = [f"{selected_ticker} Price"]
if show_volume: subplot_titles.append("Volume")
if show_macd:   subplot_titles.append("MACD")
if show_rsi:    subplot_titles.append("RSI (14)")

fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                    vertical_spacing=0.03, row_heights=row_heights,
                    subplot_titles=subplot_titles)

# Candlestick
fig.add_trace(go.Candlestick(
    x=df["Date"], open=df["Open"], high=df["High"],
    low=df["Low"], close=df["Close"], name="OHLC",
    increasing_line_color="#64ffda", decreasing_line_color="#ff6b6b"
), row=1, col=1)

if show_sma:
    for sma, color in [("SMA_20", "#f4a261"), ("SMA_50", "#e76f51"), ("SMA_200", "#a8dadc")]:
        fig.add_trace(go.Scatter(x=df["Date"], y=df[sma], name=sma,
                                  line=dict(color=color, width=1.2), opacity=0.8), row=1, col=1)

if show_bb:
    fig.add_trace(go.Scatter(x=df["Date"], y=df["BB_Upper"], name="BB Upper",
                              line=dict(color="#9b59b6", width=1, dash="dot"), opacity=0.6), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["BB_Lower"], name="BB Lower",
                              line=dict(color="#9b59b6", width=1, dash="dot"),
                              fill='tonexty', fillcolor='rgba(155,89,182,0.07)', opacity=0.6), row=1, col=1)

current_row = 2
if show_volume:
    colors = ["#64ffda" if r >= 0 else "#ff6b6b" for r in df["Daily_Return"].fillna(0)]
    fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume",
                          marker_color=colors, opacity=0.7), row=current_row, col=1)
    current_row += 1

if show_macd:
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], name="MACD",
                              line=dict(color="#64ffda", width=1.5)), row=current_row, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD_Signal"], name="Signal",
                              line=dict(color="#f4a261", width=1.5)), row=current_row, col=1)
    hist_colors = ["#64ffda" if v >= 0 else "#ff6b6b" for v in df["MACD_Hist"].fillna(0)]
    fig.add_trace(go.Bar(x=df["Date"], y=df["MACD_Hist"], name="Histogram",
                          marker_color=hist_colors, opacity=0.6), row=current_row, col=1)
    current_row += 1

if show_rsi:
    fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI"], name="RSI",
                              line=dict(color="#a8dadc", width=1.5)), row=current_row, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#ff6b6b", opacity=0.5, row=current_row, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#64ffda", opacity=0.5, row=current_row, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="#ff6b6b", opacity=0.05, row=current_row, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="#64ffda", opacity=0.05, row=current_row, col=1)

fig.update_layout(
    height=650 + (150 * (rows - 1)),
    template="plotly_dark",
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    showlegend=True,
    legend=dict(orientation="h", y=1.02, x=0),
    xaxis_rangeslider_visible=False,
    margin=dict(l=0, r=0, t=40, b=0),
    font=dict(family="monospace"),
)
st.plotly_chart(fig, use_container_width=True)


# ── Multi-ticker Comparison ────────────────────────────────────────────────────
if len(tickers) > 1:
    st.markdown('<div class="section-title">Multi-Ticker Comparison</div>', unsafe_allow_html=True)
    try:
        with st.spinner("Loading comparison data…"):
            multi_df = fetch_multi(tickers, start_str, end_str)

        if multi_df.empty or len(multi_df) < 2:
            st.warning("Not enough shared historical data to compare these tickers.")
            st.info("How to fix it: use fewer tickers, choose liquid symbols, or expand the date range.")
        else:
            tab1, tab2, tab3 = st.tabs(["📈 Normalized Returns", "🔥 Correlation Heatmap", "⚖️ Pairs Spread"])

            with tab1:
                norm = multi_df / multi_df.iloc[0] * 100
                fig2 = px.line(norm, template="plotly_dark",
                               labels={"value": "Indexed (Base=100)", "Date": ""},
                               color_discrete_sequence=px.colors.qualitative.Safe)
                fig2.update_layout(paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                                   height=380, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig2, use_container_width=True)

            with tab2:
                returns_df = multi_df.pct_change().dropna()
                corr = returns_df.corr()
                fig3 = px.imshow(corr, color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                                 text_auto=".2f", template="plotly_dark",
                                 title="Daily Returns Correlation")
                fig3.update_layout(paper_bgcolor="#0f1117", height=400, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig3, use_container_width=True)

            with tab3:
                if len(tickers) >= 2:
                    t1, t2 = st.columns(2)
                    with t1:
                        pair_a = st.selectbox("Ticker A", tickers, index=0)
                    with t2:
                        pair_b = st.selectbox("Ticker B", tickers, index=min(1, len(tickers)-1))
                    if pair_a != pair_b and pair_a in multi_df.columns and pair_b in multi_df.columns:
                        hedge = multi_df[pair_a].mean() / multi_df[pair_b].mean()
                        spread = multi_df[pair_a] - multi_df[pair_b] * hedge
                        z_score = (spread - spread.mean()) / spread.std()

                        fig4 = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                             subplot_titles=["Price Spread", "Z-Score"],
                                             vertical_spacing=0.1, row_heights=[0.5, 0.5])
                        fig4.add_trace(go.Scatter(x=spread.index, y=spread, name="Spread",
                                                   line=dict(color="#a8dadc", width=1.5)), row=1, col=1)
                        fig4.add_trace(go.Scatter(x=z_score.index, y=z_score, name="Z-Score",
                                                   line=dict(color="#f4a261", width=1.5)), row=2, col=1)
                        for level, color in [(2, "#ff6b6b"), (-2, "#64ffda"), (0, "#8892b0")]:
                            fig4.add_hline(y=level, line_dash="dot", line_color=color, opacity=0.6, row=2, col=1)

                        fig4.update_layout(template="plotly_dark", paper_bgcolor="#0f1117",
                                           plot_bgcolor="#0f1117", height=400,
                                           margin=dict(l=0, r=0, t=40, b=0))
                        st.plotly_chart(fig4, use_container_width=True)

                        buy_signals = z_score[z_score < -2]
                        sell_signals = z_score[z_score > 2]
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Current Z-Score", f"{z_score.iloc[-1]:.2f}")
                        c2.metric("Buy Signals (z<-2)", len(buy_signals))
                        c3.metric("Sell Signals (z>2)", len(sell_signals))
    except Exception as e:
        show_user_friendly_error("Multi-ticker comparison", e)


# ── Risk Analytics ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Risk & Return Analytics</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)

try:
    with c1:
        returns = df["Daily_Return"].dropna()
        if returns.empty:
            raise ValueError("Not enough return observations for risk analytics")
        fig5 = px.histogram(returns, nbins=80, template="plotly_dark",
                            labels={"value": "Daily Return", "count": "Frequency"},
                            title="Return Distribution",
                            color_discrete_sequence=["#64ffda"])
        var_95 = np.percentile(returns, 5)
        fig5.add_vline(x=var_95, line_dash="dash", line_color="#ff6b6b",
                       annotation_text=f"VaR 95%: {var_95:.2%}", annotation_font_color="#ff6b6b")
        fig5.update_layout(paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                           height=320, margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        st.plotly_chart(fig5, use_container_width=True)

    with c2:
        fig6 = go.Figure()
        fig6.add_trace(go.Scatter(x=df["Date"], y=df["Volatility_30d"] * 100,
                                   name="30d Realized Vol (%)",
                                   line=dict(color="#f4a261", width=1.5),
                                   fill="tozeroy", fillcolor="rgba(244,162,97,0.15)"))
        fig6.update_layout(template="plotly_dark", paper_bgcolor="#0f1117",
                           plot_bgcolor="#0f1117", height=320,
                           title="30-Day Rolling Volatility (%)",
                           margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig6, use_container_width=True)

    # Risk stats table
    total_return = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1)
    sharpe = returns.mean() / returns.std() * np.sqrt(252)
    rolling_max = df["Close"].cummax()
    drawdown = (df["Close"] - rolling_max) / rolling_max
    max_dd = drawdown.min()

    risk_data = pd.DataFrame({
        "Metric": ["Total Return", "Annualized Volatility", "Sharpe Ratio (rf=0)", "Max Drawdown", "VaR 95% (1-day)", "Skewness", "Kurtosis"],
        "Value": [
            f"{total_return:.2%}",
            f"{returns.std() * np.sqrt(252):.2%}",
            f"{sharpe:.2f}",
            f"{max_dd:.2%}",
            f"{var_95:.2%}",
            f"{returns.skew():.2f}",
            f"{returns.kurtosis():.2f}",
        ]
    })
    st.dataframe(risk_data, use_container_width=True, hide_index=True)
except Exception as e:
    show_user_friendly_error("Risk analytics", e)


# ── Prophet Forecast ───────────────────────────────────────────────────────────
if run_forecast:
    st.markdown('<div class="section-title">🔮 Prophet Price Forecast</div>', unsafe_allow_html=True)
    try:
        from prophet import Prophet
        df_prophet = df[["Date", "Close"]].rename(columns={"Date": "ds", "Close": "y"})
        with st.spinner("Training Prophet model…"):
            m = Prophet(daily_seasonality=False, yearly_seasonality=True,
                        weekly_seasonality=True, uncertainty_samples=200)
            m.fit(df_prophet)
            future = m.make_future_dataframe(periods=forecast_days)
            forecast = m.predict(future)

        fig7 = go.Figure()
        fig7.add_trace(go.Scatter(x=df_prophet["ds"], y=df_prophet["y"],
                                   name="Actual", line=dict(color="#64ffda", width=1.5)))
        fig7.add_trace(go.Scatter(x=forecast["ds"], y=forecast["yhat"],
                                   name="Forecast", line=dict(color="#f4a261", width=2, dash="dash")))
        fig7.add_trace(go.Scatter(
            x=pd.concat([forecast["ds"], forecast["ds"][::-1]]),
            y=pd.concat([forecast["yhat_upper"], forecast["yhat_lower"][::-1]]),
            fill="toself", fillcolor="rgba(244,162,97,0.15)",
            line=dict(color="rgba(255,255,255,0)"), name="95% CI"
        ))
        fig7.add_vline(x=df_prophet["ds"].max(), line_dash="dot",
                       line_color="#8892b0", annotation_text="Forecast Start")
        fig7.update_layout(template="plotly_dark", paper_bgcolor="#0f1117",
                           plot_bgcolor="#0f1117", height=420,
                           title=f"{selected_ticker} — {forecast_days}-Day Prophet Forecast",
                           margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig7, use_container_width=True)

        last_actual = df["Close"].iloc[-1]
        last_forecast = forecast[forecast["ds"] > df_prophet["ds"].max()].iloc[-1]
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("Current Price", f"${last_actual:.2f}")
        fc2.metric(f"Forecast ({forecast_days}d)", f"${last_forecast['yhat']:.2f}",
                   f"{(last_forecast['yhat']/last_actual - 1):.2%}")
        fc3.metric("Forecast Range", f"${last_forecast['yhat_lower']:.2f} – ${last_forecast['yhat_upper']:.2f}")

    except ImportError:
        st.warning("Prophet not installed. Run: `pip install prophet`")
    except Exception as e:
        show_user_friendly_error("Forecast", e)


# ── Raw Data ────────────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data"):
    display_cols = ["Date", "Open", "High", "Low", "Close", "Volume",
                    "Daily_Return", "SMA_20", "SMA_50", "RSI", "MACD"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].tail(60).style.format({
        "Close": "${:.2f}", "Open": "${:.2f}", "High": "${:.2f}", "Low": "${:.2f}",
        "Daily_Return": "{:.2%}", "RSI": "{:.1f}", "MACD": "{:.3f}",
        "SMA_20": "${:.2f}", "SMA_50": "${:.2f}",
    }), use_container_width=True)
    csv = df[display_cols].to_csv(index=False)
    st.download_button("⬇️ Download CSV", csv, f"{selected_ticker}_analysis.csv", "text/csv")