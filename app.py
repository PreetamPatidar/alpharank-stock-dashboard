"""
Multi-Factor Stock Ranking Web Dashboard
Built with Streamlit, Pandas, Plotly, and yfinance.
Supports All Registered Stocks on NSE & BSE (India) as well as Global / US Equities.

Features:
- Live data fetching for ROE, Debt/Equity, Trailing P/E, 50 & 200 SMA
- Multi-factor scoring engine (Efficiency 35%, Financial Risk 30%, Valuation 25%, Momentum 10%)
- Interactive sortable data table with conditional color formatting (>70 Green, 40-70 Yellow, <40 Red)
- Comprehensive NSE & BSE Directory (2,600+ companies) with live search and index baskets
- Plotly horizontal ranking bar chart, radar score profile, and factor contribution breakdown
- 1-Year historical technical chart with 50 & 200-day moving averages
- Multi-threaded parallel data fetching and disk caching
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any

# Local modules
from scoring import (
    calculate_multi_factor_rankings,
    WEIGHTS as DEFAULT_WEIGHTS,
)
from data_loader import (
    fetch_batch_data,
    fetch_single_ticker_history,
    load_master_nse_directory,
    get_available_watchlists,
    format_ticker_symbol,
    clear_disk_cache,
)
from charts import (
    create_horizontal_ranking_chart,
    create_factor_breakdown_radar,
    create_factor_contribution_bar,
    create_price_sma_chart,
    create_all_stocks_factor_comparison,
    get_score_color,
    COLOR_STRONG,
    COLOR_NEUTRAL,
    COLOR_WEAK,
)

# Page configuration
st.set_page_config(
    page_title="AlphaRank | Multi-Factor Stock Dashboard (NSE & BSE)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for high-end Financial Terminal aesthetic
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Terminal header styling */
    .terminal-title {
        background: linear-gradient(135deg, #60A5FA 0%, #3B82F6 40%, #10B981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.3rem;
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem;
    }
    
    .terminal-subtitle {
        color: #9CA3AF;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    
    /* Metric Cards */
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(96, 165, 250, 0.4);
    }
    .metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94A3B8;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #F8FAFC;
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 4px;
    }
    
    /* Badges */
    .badge-green {
        background: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-yellow {
        background: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-red {
        background: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    
    /* Tab formatting */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 18px;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# Load master registered stock directory
master_nse_df = load_master_nse_directory()

# SIDEBAR: Exchange & Market Selection
st.sidebar.markdown("## 🏛️ Exchange & Market")

selected_market = st.sidebar.radio(
    "Choose Market:",
    options=["🇮🇳 National Stock Exchange (NSE)", "🇮🇳 Bombay Stock Exchange (BSE)", "🇺🇸 US / Global Markets"],
    index=0
)

exchange_code = "NSE" if "NSE" in selected_market else ("BSE" if "BSE" in selected_market else "US")
ticker_suffix = ".NS" if exchange_code == "NSE" else (".BO" if exchange_code == "BSE" else "")
curr_symbol = "₹" if exchange_code in ["NSE", "BSE"] else "$"

# Load available watchlists for selected exchange
watchlists_dict = get_available_watchlists(exchange_code)

st.sidebar.markdown("---")
st.sidebar.markdown("## 📂 Watchlist & Stock Selection")

selection_mode = st.sidebar.selectbox(
    "Selection Mode:",
    options=[
        "Predefined Index / Basket",
        "🔍 Search All Registered Stocks (NSE & BSE)",
        "✏️ Custom Ticker Input"
    ],
    index=0
)

final_tickers = []

if selection_mode == "Predefined Index / Basket":
    # Filter watchlists based on market
    if exchange_code in ["NSE", "BSE"]:
        avail_keys = [k for k in watchlists_dict.keys() if "🇮🇳" in k]
    else:
        avail_keys = [k for k in watchlists_dict.keys() if "🇺🇸" in k]
        
    selected_basket = st.sidebar.selectbox(
        "Choose Index / Basket:",
        options=avail_keys,
        index=0
    )
    basket_tickers = watchlists_dict.get(selected_basket, [])
    
    # If it's a large index like NIFTY 500 or NIFTY Midcap 150, allow batch limit
    if len(basket_tickers) > 50:
        batch_limit = st.sidebar.select_slider(
            f"Select Number of Stocks from {selected_basket}:",
            options=[25, 50, 100, 150, 250, len(basket_tickers)],
            value=min(50, len(basket_tickers)),
            help="Process in batches for optimal speed"
        )
        final_tickers = basket_tickers[:batch_limit]
    else:
        final_tickers = basket_tickers

elif selection_mode == "🔍 Search All Registered Stocks (NSE & BSE)":
    st.sidebar.markdown(f"**Total Registered Companies:** `{len(master_nse_df):,}`")
    
    # Search filter by company name or ticker
    search_query = st.sidebar.text_input("🔎 Search by Company Name or Symbol:", placeholder="e.g. Tata, Reliance, Infosys, Zomato...")
    
    filtered_df = master_nse_df.copy()
    if search_query.strip():
        q = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["symbol"].str.lower().str.contains(q, na=False) |
            filtered_df["company_name"].str.lower().str.contains(q, na=False)
        ]
        
    st.sidebar.caption(f"Showing {len(filtered_df)} matching companies")
    
    # Create options dict: "SYMBOL - Company Name" -> Ticker
    stock_options = {}
    col_t = "nse_ticker" if exchange_code == "NSE" else "bse_ticker"
    
    for _, r in filtered_df.head(150).iterrows():
        label = f"{r['symbol']} ({r['company_name'][:32]})"
        stock_options[label] = r[col_t] if pd.notna(r[col_t]) else f"{r['symbol']}{ticker_suffix}"
        
    default_selected = list(stock_options.keys())[:10] if stock_options else []
    
    picked_labels = st.sidebar.multiselect(
        "Select Companies to Rank:",
        options=list(stock_options.keys()),
        default=default_selected,
        help="Select any combination of stocks from the registered directory"
    )
    final_tickers = [stock_options[lbl] for lbl in picked_labels]

else:  # Custom Ticker Input
    default_str = "RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, BHARTIARTL, ITC, SBIN" if exchange_code in ["NSE", "BSE"] else "AAPL, MSFT, GOOGL, NVDA, TSLA"
    user_str = st.sidebar.text_area(
        "Enter Tickers (comma-separated):",
        value=default_str,
        height=100,
        help=f"Tickers without suffix will automatically use {ticker_suffix}"
    )
    raw_list = [t.strip().upper() for t in user_str.split(",") if t.strip()]
    final_tickers = [format_ticker_symbol(t, exchange_code) for t in raw_list]


# Advanced Scoring Weight Customization
with st.sidebar.expander("⚖️ Scoring Engine Weights", expanded=False):
    st.caption("Default weights match the Multi-Factor methodology:")
    w_eff = st.slider("Efficiency (ROE)", min_value=0.0, max_value=1.0, value=0.35, step=0.05)
    w_risk = st.slider("Financial Risk (D/E)", min_value=0.0, max_value=1.0, value=0.30, step=0.05)
    w_val = st.slider("Valuation (P/E)", min_value=0.0, max_value=1.0, value=0.25, step=0.05)
    w_mom = st.slider("Momentum (SMA)", min_value=0.0, max_value=1.0, value=0.10, step=0.05)
    
    total_w = w_eff + w_risk + w_val + w_mom
    if round(total_w, 2) != 1.00:
        st.warning(f"⚠️ Total weight is {total_w:.2f}. Scores will be normalized to 100%.")
        active_weights = {
            "efficiency": w_eff / total_w if total_w > 0 else 0.25,
            "financial_risk": w_risk / total_w if total_w > 0 else 0.25,
            "valuation": w_val / total_w if total_w > 0 else 0.25,
            "momentum": w_mom / total_w if total_w > 0 else 0.25,
        }
    else:
        active_weights = {
            "efficiency": w_eff,
            "financial_risk": w_risk,
            "valuation": w_val,
            "momentum": w_mom,
        }

# Action Buttons
col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    btn_fetch = st.button("🚀 Analyze & Rank", type="primary", use_container_width=True)
with col_btn2:
    if st.button("🔄 Refresh Live", use_container_width=True, help="Bypass local cache and fetch fresh live quotes"):
        clear_disk_cache(final_tickers)
        if "metrics_df" in st.session_state:
            del st.session_state["metrics_df"]
        st.session_state["force_refresh"] = True
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Score Rating Categories:**
    - 🟢 **Score > 70:** Strong Buy / Quality Leader
    - 🟡 **Score 40 - 70:** Hold / Neutral Quality
    - 🔴 **Score < 40:** High Risk / Underperforming
    """
)
st.sidebar.caption("Data source: NSE, BSE & Yahoo Finance")


# MAIN DASHBOARD HEADER
st.markdown('<div class="terminal-title">AlphaRank Multi-Factor Stock Dashboard</div>', unsafe_allow_html=True)
market_badge = f"<span style='color: #60A5FA; font-weight: 600;'>{selected_market}</span>"
st.markdown(
    f'<div class="terminal-subtitle">'
    f'Active Market: {market_badge} • Analyzing Return on Equity (35%), Debt-to-Equity (30%), '
    f'Batch-relative P/E Valuation (25%), and 50/200-day Moving Average Momentum (10%).'
    '</div>',
    unsafe_allow_html=True
)

if not final_tickers:
    st.info("👈 Please select stocks or an index from the sidebar to begin ranking.")
    st.stop()


# FETCH & PROCESS DATA (Cached in session_state to prevent re-fetching on tab clicks)
current_batch_key = f"{exchange_code}_{selection_mode}_{'|'.join(sorted(final_tickers))}"
is_new_tickers = st.session_state.get("last_batch_key") != current_batch_key
force_refresh = st.session_state.pop("force_refresh", False)

if btn_fetch or is_new_tickers or force_refresh or "metrics_df" not in st.session_state:
    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    def update_progress(done, total):
        progress_placeholder.progress(done / total)
        status_placeholder.caption(f"⚡ Fetching fundamentals & moving averages: {done}/{total} stocks completed...")

    with st.spinner(f"Evaluating {len(final_tickers)} stocks across 4 quantitative factors..."):
        metrics_df, _, failed_tickers = fetch_batch_data(
            final_tickers,
            max_workers=10,
            progress_callback=update_progress,
            use_cache=not force_refresh
        )

    progress_placeholder.empty()
    status_placeholder.empty()
    st.session_state["metrics_df"] = metrics_df
    st.session_state["failed_tickers"] = failed_tickers
    st.session_state["last_batch_key"] = current_batch_key
else:
    metrics_df = st.session_state["metrics_df"]
    failed_tickers = st.session_state.get("failed_tickers", [])

if failed_tickers:
    st.warning(f"⚠️ Note: {len(failed_tickers)} tickers could not be retrieved: {', '.join(failed_tickers[:8])}{'...' if len(failed_tickers)>8 else ''}")

if metrics_df.empty:
    st.error("No valid stock data could be fetched. Please verify the selected tickers.")
    st.stop()

# Compute Rankings via Scoring Engine using active user weights
ranked_df = calculate_multi_factor_rankings(metrics_df, active_weights)


# TOP METRIC SUMMARY CARDS
col_m1, col_m2, col_m3, col_m4 = st.columns(4)

top_stock = ranked_df.iloc[0]
valid_pe = ranked_df["trailingPE"][(ranked_df["trailingPE"].notna()) & (ranked_df["trailingPE"] > 0)]
batch_median_pe = valid_pe.median() if not valid_pe.empty else 0.0

valid_roe = ranked_df["returnOnEquity"].dropna()
avg_roe = (valid_roe * 100).mean() if not valid_roe.empty else 0.0

# Calculate momentum leaders (Price > 50 SMA > 200 SMA)
momentum_leaders_count = sum(
    (row["currentPrice"] > row["sma50"] > row["sma200"])
    for _, row in ranked_df.iterrows()
    if pd.notna(row["sma50"]) and pd.notna(row["sma200"])
)

with col_m1:
    top_color = get_score_color(top_stock["investment_score"])
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">🏆 Top Ranked Asset</div>
            <div class="metric-value" style="color: {top_color};">{top_stock['ticker']}</div>
            <div class="metric-sub">Score: <b>{top_stock['investment_score']} / 100</b> ({top_stock['rating'].split('/')[0].strip()})</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_m2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">📊 Batch Median P/E</div>
            <div class="metric-value">{batch_median_pe:.1f}x</div>
            <div class="metric-sub">Valuation anchor across {len(valid_pe)} profitable stocks</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_m3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">⚡ Average ROE (Efficiency)</div>
            <div class="metric-value">{avg_roe:.1f}%</div>
            <div class="metric-sub">Across {len(ranked_df)} analyzed companies</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_m4:
    pct_bullish = (momentum_leaders_count / len(ranked_df)) * 100 if len(ranked_df) > 0 else 0
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">🚀 Bullish Momentum</div>
            <div class="metric-value">{momentum_leaders_count} / {len(ranked_df)}</div>
            <div class="metric-sub">{pct_bullish:.0f}% Golden Trend (P > 50 > 200 SMA)</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.write("")


# DASHBOARD TABS
tab_rankings, tab_charts, tab_single_stock, tab_directory, tab_methodology = st.tabs([
    "📋 Interactive Rankings Table",
    "📊 Comparative Visualizations",
    "🔍 Deep-Dive Stock Analysis",
    "🏢 All Registered Stocks Directory",
    "📖 Scoring Engine Logic",
])


# TAB 1: INTERACTIVE RANKINGS TABLE WITH CONDITIONAL FORMATTING
with tab_rankings:
    col_t_header, col_filter = st.columns([2, 1])
    with col_t_header:
        st.markdown(f"### 🏆 Master Investment Score Leaderboard ({len(ranked_df)} Stocks)")
        st.caption(f"Sort any column by clicking the header. Color coding: 🟢 >70 (Strong) | 🟡 40-70 (Neutral) | 🔴 <40 (Weak)")
        
    with col_filter:
        rating_filter = st.multiselect(
            "Filter by Rating Tier:",
            options=["Strong Buy / Outperform", "Hold / Neutral", "Underperform / High Risk"],
            default=["Strong Buy / Outperform", "Hold / Neutral", "Underperform / High Risk"]
        )

    # Filtered dataframe
    filtered_ranked_df = ranked_df[ranked_df["rating"].isin(rating_filter)].copy() if rating_filter else ranked_df.copy()
    display_df = filtered_ranked_df.copy()
    
    # Formatted display columns with resilient null handling
    def _safe_roe(x):
        try:
            return f"{float(x) * 100:.1f}%" if pd.notna(x) else "N/A"
        except Exception:
            return "N/A"

    def _safe_de(x):
        try:
            if pd.isna(x):
                return "N/A"
            v = float(x)
            return f"{v / 100.0:.2f}x" if v > 10.0 else f"{v:.2f}x"
        except Exception:
            return "N/A"

    def _safe_pe(x):
        try:
            if pd.isna(x):
                return "N/A"
            v = float(x)
            return f"{v:.1f}x" if v > 0 else "Loss"
        except Exception:
            return "N/A"

    def _safe_currency(x):
        try:
            return f"{curr_symbol} {float(x):,.2f}" if pd.notna(x) else "N/A"
        except Exception:
            return "N/A"

    display_df["ROE (%)"] = display_df["returnOnEquity"].apply(_safe_roe)
    display_df["D/E Ratio"] = display_df["debtToEquity"].apply(_safe_de)
    display_df["Trailing P/E"] = display_df["trailingPE"].apply(_safe_pe)
    display_df["Current Price"] = display_df["currentPrice"].apply(_safe_currency)
    display_df["50 SMA"] = display_df["sma50"].apply(_safe_currency)
    display_df["200 SMA"] = display_df["sma200"].apply(_safe_currency)
    
    # Momentum tag
    def get_mom_tag(row):
        try:
            p = float(row["currentPrice"]) if pd.notna(row["currentPrice"]) else None
            s50 = float(row["sma50"]) if pd.notna(row["sma50"]) else None
            s200 = float(row["sma200"]) if pd.notna(row["sma200"]) else None
            if p is None or s50 is None or s200 is None:
                return "N/A"
            if p > s50 > s200:
                return "🟢 Bullish (P>50>200)"
            elif p > s50 and p > s200:
                return "🟡 Above MAs"
            elif s50 > s200:
                return "🟡 Golden Cross (Pullback)"
            else:
                return "🔴 Bearish Trend"
        except Exception:
            return "N/A"
            
    display_df["Momentum Alignment"] = display_df.apply(get_mom_tag, axis=1)

    # Styling helper
    def color_score_column(val):
        try:
            score = float(val)
            if score >= 70.0:
                return "background-color: rgba(16, 185, 129, 0.25); color: #10B981; font-weight: bold;"
            elif score >= 40.0:
                return "background-color: rgba(245, 158, 11, 0.25); color: #F59E0B; font-weight: bold;"
            else:
                return "background-color: rgba(239, 68, 68, 0.25); color: #EF4444; font-weight: bold;"
        except:
            return ""

    def color_subscores(val):
        try:
            score = float(val)
            if score >= 70.0:
                return "color: #10B981; font-weight: 600;"
            elif score >= 40.0:
                return "color: #F59E0B; font-weight: 600;"
            else:
                return "color: #EF4444; font-weight: 600;"
        except:
            return ""

    table_cols = [
        "rank", "ticker", "name", "investment_score", "rating",
        "efficiency_score", "financial_risk_score", "valuation_score", "momentum_score",
        "Current Price", "ROE (%)", "D/E Ratio", "Trailing P/E", "50 SMA", "200 SMA", "Momentum Alignment"
    ]
    
    col_rename = {
        "rank": "Rank",
        "ticker": "Ticker",
        "name": "Company Name",
        "investment_score": "Investment Score (0-100)",
        "rating": "Rating",
        "efficiency_score": "Efficiency Sub-Score (35%)",
        "financial_risk_score": "Risk Sub-Score (30%)",
        "valuation_score": "Valuation Sub-Score (25%)",
        "momentum_score": "Momentum Sub-Score (10%)",
    }
    
    styler_obj = display_df[table_cols].rename(columns=col_rename).style
    map_func = getattr(styler_obj, "map", getattr(styler_obj, "applymap", None))
    styled_table = map_func(
        color_score_column, subset=["Investment Score (0-100)"]
    )
    map_func_2 = getattr(styled_table, "map", getattr(styled_table, "applymap", None))
    styled_table = map_func_2(
        color_subscores, subset=[
            "Efficiency Sub-Score (35%)",
            "Risk Sub-Score (30%)",
            "Valuation Sub-Score (25%)",
            "Momentum Sub-Score (10%)"
        ]
    ).format(
        {"Investment Score (0-100)": "{:.1f}",
         "Efficiency Sub-Score (35%)": "{:.1f}",
         "Risk Sub-Score (30%)": "{:.1f}",
         "Valuation Sub-Score (25%)": "{:.1f}",
         "Momentum Sub-Score (10%)": "{:.1f}"}
    )

    st.dataframe(
        styled_table,
        use_container_width=True,
        height=min(650, max(280, len(display_df) * 42 + 50))
    )

    # Download CSV
    csv_data = ranked_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=f"📥 Export Full Scored Dataset to CSV ({len(ranked_df)} Stocks)",
        data=csv_data,
        file_name=f"alpharank_{exchange_code.lower()}_stock_scores.csv",
        mime="text/csv",
    )


# TAB 2: COMPARATIVE VISUALIZATIONS
with tab_charts:
    st.markdown("### 📊 Cross-Stock Factor Comparison")
    
    # If batch is large (e.g. >30), let user choose how many top/bottom to plot for visual clarity
    if len(ranked_df) > 30:
        plot_limit = st.slider("Number of top-ranked stocks to visualize:", min_value=10, max_value=min(60, len(ranked_df)), value=25)
        chart_df = ranked_df.head(plot_limit)
    else:
        chart_df = ranked_df
        
    col_chart_left, col_chart_right = st.columns([1, 1])
    
    with col_chart_left:
        st.markdown(f"#### Overall Investment Scores (Top {len(chart_df)})")
        fig_bar = create_horizontal_ranking_chart(chart_df)
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_chart_right:
        st.markdown(f"#### Factor Sub-Scores Comparison (Top {len(chart_df)})")
        fig_comparison = create_all_stocks_factor_comparison(chart_df)
        st.plotly_chart(fig_comparison, use_container_width=True)


# TAB 3: DEEP-DIVE INDIVIDUAL STOCK ANALYSIS
with tab_single_stock:
    st.markdown("### 🔍 Single Stock Factor & Technical Breakdown")
    
    ticker_options = ranked_df["ticker"].tolist()
    selected_ticker = st.selectbox(
        "Select a stock for granular factor breakdown and technical SMA chart:",
        options=ticker_options,
        index=0
    )
    
    stock_row = ranked_df[ranked_df["ticker"] == selected_ticker].iloc[0]
    stock_color = get_score_color(stock_row["investment_score"])
    
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <h2 style="margin: 0; color: #F8FAFC;">{stock_row['ticker']} - {stock_row['name']}</h2>
                    <span style="color: #94A3B8; font-size: 0.95rem;">Sector: {stock_row['sector']} | Price: <b>{curr_symbol} {stock_row['currentPrice']:,.2f}</b></span>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 2.2rem; font-weight: 800; color: {stock_color}; font-family: monospace;">
                        {stock_row['investment_score']} <span style="font-size: 1rem; color: #94A3B8;">/ 100</span>
                    </div>
                    <span style="font-weight: 600; font-size: 0.9rem; color: {stock_color};">Rank #{stock_row['rank']} • {stock_row['rating']}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    col_dd1, col_dd2 = st.columns(2)
    with col_dd1:
        fig_radar = create_factor_breakdown_radar(stock_row)
        st.plotly_chart(fig_radar, use_container_width=True)
        
    with col_dd2:
        fig_contrib = create_factor_contribution_bar(stock_row, active_weights)
        st.plotly_chart(fig_contrib, use_container_width=True)

    # Technical Chart
    st.markdown("#### 📈 Technical Trend & Moving Average Alignment")
    with st.spinner(f"Loading historical chart for {selected_ticker}..."):
        hist_df = fetch_single_ticker_history(selected_ticker)
        
    if not hist_df.empty:
        fig_sma = create_price_sma_chart(
            selected_ticker,
            hist_df,
            stock_row["sma50"] if pd.notna(stock_row["sma50"]) else 0,
            stock_row["sma200"] if pd.notna(stock_row["sma200"]) else 0
        )
        st.plotly_chart(fig_sma, use_container_width=True)
    else:
        st.info("Historical price data not available for technical SMA plot.")


# TAB 4: ALL REGISTERED STOCKS DIRECTORY
with tab_directory:
    st.markdown("### 🏢 Master Registered Equities Directory (NSE & BSE)")
    st.caption(f"Comprehensive directory of {len(master_nse_df):,} companies officially registered on the National Stock Exchange and Bombay Stock Exchange.")
    
    col_dir_s, col_dir_ser = st.columns([2, 1])
    with col_dir_s:
        dir_search = st.text_input("Filter directory by Name or Symbol:", placeholder="e.g. Tata, HDFC, Mahindra, Adani...", key="dir_search_input")
    with col_dir_ser:
        series_filter = st.multiselect("Series / Category:", options=master_nse_df["series"].unique().tolist(), default=["EQ"])
        
    dir_view_df = master_nse_df.copy()
    if dir_search.strip():
        q_d = dir_search.strip().lower()
        dir_view_df = dir_view_df[
            dir_view_df["symbol"].str.lower().str.contains(q_d, na=False) |
            dir_view_df["company_name"].str.lower().str.contains(q_d, na=False)
        ]
    if series_filter:
        dir_view_df = dir_view_df[dir_view_df["series"].isin(series_filter)]
        
    st.dataframe(
        dir_view_df.rename(columns={
            "symbol": "Symbol",
            "company_name": "Company Name",
            "series": "Series",
            "nse_ticker": "NSE Ticker (.NS)",
            "bse_ticker": "BSE Ticker (.BO)"
        })[["Symbol", "Company Name", "Series", "NSE Ticker (.NS)", "BSE Ticker (.BO)"]],
        use_container_width=True,
        height=500
    )
    
    st.info("💡 **Tip:** Copy any ticker from above into the Custom Ticker area or use the sidebar search to immediately rank its investment score!")


# TAB 5: METHODOLOGY & LOGIC
with tab_methodology:
    st.markdown("### 📖 Scoring Engine Mathematical Specification")
    
    st.markdown(
        """
        The multi-factor ranking model synthesizes four foundational investment vectors into a single 0-100 normalized score:
        
        $$ \\text{Investment Score} = 0.35 \\times \\text{Efficiency} + 0.30 \\times \\text{Risk} + 0.25 \\times \\text{Valuation} + 0.10 \\times \\text{Momentum} $$
        
        ---
        
        #### 1. Efficiency Factor (35% Weight)
        - **Metric:** Return on Equity (ROE = Net Income / Shareholder's Equity).
        - **Logic:**
          - If $\\text{ROE} \\le 0$, the sub-score is **penalized to 0.0**. Negative ROE signifies capital destruction.
          - If $\\text{ROE} > 0$, scales monotonically up to $100$ based on batch percentile ranking and benchmark scaling ($30\\%+$ ROE benchmarked as tier-1 capital allocation).
          
        #### 2. Financial Risk Factor (30% Weight)
        - **Metric:** Debt-to-Equity (D/E = Total Debt / Total Stockholder Equity).
        - **Logic:**
          - Zero debt $(\\text{D/E} = 0)$ is rewarded with maximum points ($100.0$).
          - Highly leveraged balance sheets with $\\text{D/E} \\ge 2.0$ receive $0.0$ points.
          - Linear decay: $\\text{Score} = 100 \\times \\frac{2.0 - \\text{D/E}}{2.0}$ for $0 < \\text{D/E} < 2.0$.
          
        #### 3. Valuation Factor (25% Weight)
        - **Metric:** Trailing Price-to-Earnings (P/E) relative to the batch median P/E ($M$).
        - **Logic:**
          - Unprofitable companies with $\\text{P/E} \\le 0$ receive $0.0$ points.
          - If $\\text{P/E} \\le M$ (cheaper than median): $\\text{Score} = 50 + 50 \\times \\frac{M - \\text{P/E}}{M}$ (up to 100 points).
          - If $\\text{P/E} > M$ (more expensive than median): $\\text{Score} = \\max\\left(0, 50 - 50 \\times \\frac{\\text{P/E} - M}{M}\\right)$.
          
        #### 4. Momentum Factor (10% Weight)
        - **Metric:** Price relation to 50-day SMA and 200-day SMA.
        - **Logic:**
          - **100 pts (Max):** $\\text{Price} > 50\\text{-day SMA} > 200\\text{-day SMA}$ (Clear Bullish Golden Alignment).
          - **75 pts:** $\\text{Price} > 50\\text{-day SMA}$ and $\\text{Price} > 200\\text{-day SMA}$.
          - **60 pts:** $50\\text{-day SMA} > 200\\text{-day SMA}$ with price pulling back between them.
          - **45 pts:** Price above 200-day SMA only.
          - **30 pts:** Price above 50-day SMA only.
          - **5 - 15 pts:** Bearish death-cross alignment (Price below both moving averages).
        """
    )
