from __future__ import annotations
from datetime import datetime
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from forecasting import scenarios
from backtesting import evaluate_historical_ranges
from market_data import load_security
from scoring import MODEL_VERSION, calculate_score
from file_store import (add_price_alert, add_watch_item, dismiss_alert,
    evaluate_price_alerts, get_alert_events, get_score_history,
    get_watch_items, initialize_store, remove_watch_item,
    save_score_run, save_stock_snapshot, DATA_DIR)

st.set_page_config(page_title="Bharat Equity Research", page_icon="📊", layout="wide")
initialize_store()
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
.stApp{background:#0b1220;color:#e5edf7}.block-container{max-width:1440px;padding-top:2rem}
[data-testid="stMetric"]{background:#111c2e;border:1px solid #253550;padding:16px;border-radius:12px}
.hero{padding:24px 28px;border:1px solid #243650;border-radius:18px;background:linear-gradient(115deg,#14243a,#102433 65%,#16322f);margin-bottom:20px}
.small{color:#93a7bd;font-size:.9rem}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div style="color:#63d6bd;font-weight:700;letter-spacing:.1em">BHARAT EQUITY RESEARCH</div><h1 style="margin:.3rem 0">Research with the assumptions in view.</h1><div class="small">Indian listed equities · explainable screening · experimental scenarios</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Find a security")
    exchange = st.radio("Exchange", ["NSE", "BSE"], horizontal=True)
    symbol_input = st.text_input("Exchange symbol", value="RELIANCE", help="Examples: RELIANCE, TCS, INFY")
    refresh = st.button("Load analysis", type="primary", use_container_width=True)
    st.divider()
    st.caption("Local watchlist · saved in files")
    watch_items = get_watch_items()
    if not watch_items:
        st.caption("No securities saved yet.")
    for item in watch_items:
        left, right = st.columns([4, 1])
        latest = get_score_history(item["symbol"], item["exchange"])
        if latest:
            run = latest[0]
            score_text = f" · score {run['score']:.1f}" if run["score"] is not None else ""
            left.caption(f"{item['symbol']} · {item['exchange']} · {run['price']:,.2f}{score_text}")
        else:
            left.caption(f"{item['symbol']} · {item['exchange']} · no saved quote")
        if right.button("×", key=f"remove-{item['id']}", help="Remove from watchlist"):
            remove_watch_item(item["symbol"], item["exchange"])
            st.rerun()
    st.divider()
    st.caption(f"Stock data files: {DATA_DIR}")

key = f"analysis:{exchange}:{symbol_input.strip().upper()}"
should_load = refresh or key not in st.session_state
if should_load:
    if symbol_input.strip():
        try:
            with st.spinner("Loading reported market data…"):
                st.session_state[key] = load_security(symbol_input, exchange)
        except Exception as exc:
            st.session_state.pop(key, None)
            st.error(str(exc))
            st.info("Check the symbol/exchange and retry. The app does not fill missing data with estimates.")

data = st.session_state.get(key)
if not data:
    st.info("Enter an NSE or BSE symbol and load the analysis. Data availability depends on the upstream provider.")
    with st.expander("Recent in-app alerts"):
        events = [e for e in get_alert_events() if not e["dismissed"]]
        if events:
            for event in events:
                st.write(f"{event['symbol']} {event['type'].replace('_',' ')} · observed {event['observed']:.2f}, threshold {event['threshold']:.2f} · {event['at']}")
        else:
            st.caption("No active alerts.")
    st.stop()

score = calculate_score(data["info"], data["technical"])
info, tech = data["info"], data["technical"]
try:
    observed_at = pd.Timestamp(data["market_timestamp"])
    observed_at = observed_at.tz_localize("UTC") if observed_at.tzinfo is None else observed_at.tz_convert("UTC")
    price_age_hours = max(0.0, (pd.Timestamp.now(tz="UTC") - observed_at).total_seconds() / 3600)
except (TypeError, ValueError):
    price_age_hours = float("inf")
price_is_stale = price_age_hours > 96
if price_is_stale:
    score.score = None
if should_load:
    prior = get_score_history(data["symbol"].split(".")[0], exchange)
    st.session_state[f"previous-score:{key}"] = prior[0]["score"] if prior else None
    if not price_is_stale:
        evaluate_price_alerts(data["symbol"].split(".")[0], exchange, tech["current_price"])
    save_score_run(data["symbol"].split(".")[0], exchange, MODEL_VERSION, score.score,
        score.coverage, tech["current_price"], str(data["market_timestamp"]), data["source"], json.dumps(score.components, default=str))
    snapshot_paths = save_stock_snapshot(data)
    st.session_state[f"snapshot-paths:{key}"] = snapshot_paths

st.subheader(f"{data['name']}  ·  {data['symbol']}")
st.caption(f"{data['sector']} · {data['currency']} · Score model {MODEL_VERSION}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest close", f"{data['currency']} {tech['current_price']:,.2f}")
previous_score = st.session_state.get(f"previous-score:{key}")
c2.metric("Research score", f"{score.score:.1f} / 100" if score.score is not None else "Unavailable",
    delta=f"{score.score - previous_score:+.1f} vs previous run" if score.score is not None and previous_score is not None else None,
    help="Not a probability of profit or a buy/sell recommendation.")
c3.metric("Input coverage", f"{score.coverage:.0f}%", help="Share of configured score weight supported by usable inputs; unavailable categories contribute zero.")
c4.metric("1-year volatility", f"{tech['annualized_volatility']:.1%}" if tech["annualized_volatility"] is not None else "Unavailable")
if price_is_stale:
    st.error(f"Latest price observation is {price_age_hours:.0f} hours old. The composite score is suppressed until fresh market data is available.")

with st.expander("Reported company metrics", expanded=True):
    fundamental_items = [
        ("Market capitalization", "marketCap", "currency"),
        ("Revenue growth", "revenueGrowth", "percent"),
        ("Earnings growth", "earningsGrowth", "percent"),
        ("Operating margin", "operatingMargins", "percent"),
        ("Profit margin", "profitMargins", "percent"),
        ("Debt / equity", "debtToEquity", "ratio"),
        ("Price / book", "priceToBook", "multiple"),
        ("Dividend yield", "dividendYield", "percent"),
        ("Beta", "beta", "number"),
    ]
    metric_columns = st.columns(3)
    for index, (label, field, kind) in enumerate(fundamental_items):
        raw = info.get(field)
        try:
            number = float(raw)
            if not pd.notna(number):
                raise ValueError
            if kind == "percent":
                rendered = f"{number:.1%}"
            elif kind == "currency":
                rendered = f"{data['currency']} {number:,.0f}"
            elif kind == "multiple":
                rendered = f"{number:.2f}x"
            elif field == "debtToEquity":
                rendered = f"{number / 100:.2f}x" if abs(number) > 10 else f"{number:.2f}x"
            else:
                rendered = f"{number:.2f}"
        except (TypeError, ValueError):
            rendered = "Not reported"
        metric_columns[index % 3].metric(label, rendered)

col_chart, col_info = st.columns([1.65, 1])
with col_chart:
    st.markdown("#### Price history")
    hist = data["history"].tail(365)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Adjusted close", line={"color":"#58c7b0","width":2}))
    for window, color in ((20,"#f0b45b"),(50,"#809cf5"),(200,"#db81d0")):
        if len(hist) >= window:
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(window).mean(), name=f"{window}-day SMA", line={"color":color,"width":1.4}))
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400, margin={"l":10,"r":10,"t":25,"b":10}, legend={"orientation":"h"}, yaxis_title=data["currency"])
    st.plotly_chart(fig, use_container_width=True)
with col_info:
    st.markdown("#### Market and risk context")
    for label, value in (
        ("RSI · 14 sessions", f"{tech['rsi14']:.1f}" if tech["rsi14"] is not None else "Unavailable"),
        ("20 / 50 / 200-day average", " / ".join(f"{tech[k]:,.2f}" if tech[k] is not None else "—" for k in ("ma20","ma50","ma200"))),
        ("6-month price change", f"{tech['return_6m']:+.1%}" if tech["return_6m"] is not None else "Unavailable"),
        ("1-year max drawdown", f"{tech['max_drawdown_1y']:.1%}" if tech["max_drawdown_1y"] is not None else "Unavailable"),
        ("Trailing P/E", f"{info['trailingPE']:.2f}" if isinstance(info.get("trailingPE"),(int,float)) and info["trailingPE"] > 0 else "Unavailable / not meaningful"),
        ("ROE", f"{info['returnOnEquity']:.1%}" if isinstance(info.get("returnOnEquity"),(int,float)) else "Unavailable"),
    ):
        st.write(f"**{label}**  ·  {value}")
    st.caption("Price alerts")
    alert_rule = st.selectbox("Condition", ["price_above", "price_below"], format_func=lambda x: "Price rises above" if x == "price_above" else "Price falls below")
    threshold = st.number_input("Threshold", min_value=0.01, value=float(tech["current_price"]), step=max(0.01, round(tech["current_price"] * .01, 2)))
    if st.button("Save price alert"):
        add_price_alert(data["symbol"].split(".")[0], exchange, threshold, alert_rule)
        st.success("Price alert saved. It is evaluated when you refresh this security.")
    if st.button("＋ Add to watchlist", key=f"watch-{key}"):
        add_watch_item(data["symbol"].split(".")[0], exchange)
        st.success("Saved to your account watchlist.")

st.divider()
tab_score, tab_scenarios, tab_backtest, tab_history, tab_alerts, tab_data = st.tabs(["Score breakdown", "Scenario range", "Historical evaluation", "Score history", "Alerts", "Data & limitations"])
with tab_score:
    st.markdown("#### Where the score comes from")
    st.dataframe(pd.DataFrame(score.components), hide_index=True, use_container_width=True)
    a, b = st.columns(2)
    with a:
        st.markdown("**Positive contributors**")
        st.write("\n".join(f"• {x}" for x in score.positives) if score.positives else "No strong contributors identified from available data.")
    with b:
        st.markdown("**Missing categories**")
        st.write(", ".join(score.missing) if score.missing else "None")
    history = get_score_history(data["symbol"].split(".")[0], exchange)
    if history:
        st.caption(f"Latest saved score run: {history[0]['score']} · saved {history[0]['calculated_at']}")
    st.caption("Model version: " + MODEL_VERSION + ". Weighted points are not rescaled when data is missing; coverage is shown separately.")
with tab_scenarios:
    st.markdown("#### Experimental volatility scenarios")
    st.warning("Unvalidated stress ranges, not price targets or guaranteed bounds. Bearish and bullish cases use ±1.645 × historical annualized volatility × √time around a flat-price baseline. Actual outcomes can fall outside this range.")
    if price_is_stale:
        st.info("Scenario calculations are suppressed because the latest price data is stale.")
    else:
        st.dataframe(scenarios(tech["current_price"], tech["annualized_volatility"]), hide_index=True, use_container_width=True)
    st.caption("No out-of-sample model validation is available yet. Scenario output is experimental and does not estimate the probability of a positive return.")
with tab_backtest:
    st.markdown("#### Chronological baseline evaluation")
    st.caption("For each monthly origin, this compares a flat-price baseline with later observed returns and measures how often the historical-volatility scenario range contained the outcome.")
    evaluation = evaluate_historical_ranges(data["history"])
    if evaluation.empty:
        st.info("At least about 2 years of price observations are needed for this retrospective evaluation.")
    else:
        st.dataframe(evaluation, hide_index=True, use_container_width=True)
    st.warning("This is a retrospective diagnostic, not a validated forecasting result. The provider may retro-adjust historical prices for corporate actions; this test does not cover delisted stocks or a point-in-time market universe, and the scenario ranges are not guaranteed bounds.")
with tab_history:
    st.markdown("#### Saved score runs")
    previous = get_score_history(data["symbol"].split(".")[0], exchange)
    if previous:
        st.dataframe(pd.DataFrame(previous), hide_index=True, use_container_width=True)
    else:
        st.info("No score history yet. Refresh the data to save a versioned score run.")
with tab_alerts:
    st.markdown("#### In-app alert history")
    events = get_alert_events()
    if not events:
        st.info("No triggered alerts yet. Alerts are evaluated when you refresh a security in this version.")
    for event in events:
        text = f"{event['symbol']} {event['type'].replace('_',' ')} {event['threshold']:.2f} · observed {event['observed']:.2f} · {event['at']}"
        if event["dismissed"]:
            st.caption("Dismissed · " + text)
        else:
            left, right = st.columns([5, 1])
            left.warning(text)
            if right.button("Dismiss", key=f"dismiss-{event['id']}"):
                dismiss_alert(event["id"])
                st.rerun()
with tab_data:
    st.markdown("#### Provenance and quality")
    st.write(f"**Source:** {data['source']}")
    st.write(f"**Instrument:** {data['symbol']} ({exchange})")
    st.write(f"**Latest market observation:** {data['market_timestamp']}")
    try:
        observed_at = pd.Timestamp(data["market_timestamp"])
        observed_at = observed_at.tz_localize("UTC") if observed_at.tzinfo is None else observed_at.tz_convert("UTC")
        st.write(f"**Age of latest price observation:** {price_age_hours:.1f} hours")
    except (TypeError, ValueError):
        st.warning("Could not determine the age of the latest price observation.")
    st.write(f"**Retrieved:** {data['retrieved_at'].strftime('%Y-%m-%d %H:%M UTC')}")
    st.write(f"**Price observations:** {data['observations']:,}")
    saved_files = st.session_state.get(f"snapshot-paths:{key}")
    if saved_files:
        st.write("**Saved company snapshot:** " + saved_files[0])
        st.write("**Saved price history CSV:** " + saved_files[1])
    st.caption("App state is stored as local JSON; stock snapshots and price history are stored as JSON and CSV files. No SQL database is used.")
    for warning in data.get("warnings", []):
        st.warning(warning)
    st.warning("This deployment uses unofficial Yahoo Finance web endpoints; it is not a licensed production data feed. Do not redistribute market data or publicly operate this service until you have verified and obtained rights for your provider, and reviewed applicable SEBI requirements. This app provides research information, not personalized advice, and does not execute trades.")

st.caption(f"Analysis calculated {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')} · Research only; no trading functionality.")
