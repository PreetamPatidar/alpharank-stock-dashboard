# 📈 AlphaRank — Multi-Factor Stock Ranking Dashboard (NSE & BSE)

AlphaRank is an interactive quantitative investment dashboard built with **Streamlit**, **Pandas**, **Plotly**, and **yfinance**. It supports all registered companies across the **National Stock Exchange (NSE)**, **Bombay Stock Exchange (BSE)**, and **US/Global Markets**.

---

## 🚀 Key Features

### 1. 🇮🇳 Comprehensive NSE & BSE Indian Markets Support
- **Master Directory**: Access **2,619+ registered equities** across NSE and BSE.
- **Predefined Indices**:
  - **NIFTY 50** (India's premier benchmark of 50 large-cap giants)
  - **BSE SENSEX 30** (Top 30 bellwether companies)
  - **NIFTY Next 50** (Next 50 high-growth large caps)
  - **NIFTY Midcap 150**
  - **NIFTY 500** (Top 500 companies representing ~96% of Indian equity free-float)
  - **Sectoral Leaders**: NIFTY Bank, NIFTY IT, NIFTY Auto, NIFTY Pharma, NIFTY FMCG, NIFTY Energy, NIFTY Metal.
- **Searchable Stock Screener**:
  - Live lookup across 2,600+ companies by name or ticker (e.g. *Tata, Reliance, Infosys, Zomato, ITC, Adani, HDFC, HAL, Coal India*).
  - Automatically appends `.NS` (NSE) or `.BO` (BSE) suffix.
  - Multi-threaded parallel data fetching with disk caching for high-speed analysis.
  - Native currency display (`₹` for Indian stocks, `$` for US stocks).

---

### 2. 🧮 Multi-Factor Quantitative Scoring Engine (0 - 100 Scale)

$$\text{Investment Score} = 0.35 \times \text{Efficiency} + 0.30 \times \text{Risk} + 0.25 \times \text{Valuation} + 0.10 \times \text{Momentum}$$

1. **Efficiency (35% Weight)**:
   - Metric: Return on Equity (ROE).
   - $\text{ROE} \le 0$: Penalized with **0 points**.
   - $\text{ROE} > 0$: Scales monotonically up to **100 points** based on benchmark targets ($30\%+$ tier-1 ROE) and batch peer ranking.
2. **Financial Risk (30% Weight)**:
   - Metric: Debt-to-Equity (D/E).
   - $\text{D/E} = 0$: **100 points** (maximum).
   - $\text{D/E} \ge 2.0$: **0 points**.
   - $0 < \text{D/E} < 2.0$: Linear interpolation $\text{Score} = 100 \times \frac{2.0 - \text{D/E}}{2.0}$.
3. **Valuation (25% Weight)**:
   - Metric: Trailing P/E compared to batch median P/E ($M$).
   - $\text{P/E} \le 0$ or loss-making: **0 points**.
   - $\text{P/E} \le M$: $\text{Score} = 50 + 50 \times \frac{M - \text{P/E}}{M}$ (cheaper stocks score up to 100).
   - $\text{P/E} > M$: $\text{Score} = \max\left(0, 50 - 50 \times \frac{\text{P/E} - M}{M}\right)$ (drops to 0 when $\ge 2M$).
4. **Momentum (10% Weight)**:
   - $\text{Current Price} > \text{50-day SMA} > \text{200-day SMA}$: Awarded **100 points** (Bullish Golden Trend).
   - Scaled lower for pullbacks above the 200 SMA (60–75 pts), recovery bounces (30–45 pts), and downtrends ($\le 15$ pts).

---

### 3. 📊 Interactive Dashboard Tabs

1. **📋 Interactive Rankings Table**:
   - Master leaderboard sorted by Investment Score.
   - Conditional color formatting: 🟢 Green ($>70$), 🟡 Yellow ($40-70$), 🔴 Red ($<40$).
   - Rating tier filtering and one-click CSV export.
2. **📊 Comparative Visualizations**:
   - Plotly horizontal bar chart of final scores with threshold benchmark lines.
   - Cross-factor grouped bar chart comparing all 4 sub-scores.
3. **🔍 Deep-Dive Stock Analysis**:
   - Radar/Spider profile chart showing factor balance.
   - Waterfall contribution breakdown (sub-scores vs weighted points).
   - 1-Year historical technical price chart with interactive 50-day and 200-day SMA lines.
4. **🏢 All Registered Stocks Directory**:
   - Interactive searchable table of all **2,619+ NSE & BSE registered companies** with symbol, company name, series, and exchange suffixes.
5. **📖 Scoring Engine Logic**:
   - Mathematical specification and reference documentation.

---

## 🏃 Quick Start

1. **Start the application**:
   ```bash
   streamlit run app.py
   ```
2. Open your browser at:
   👉 **`http://localhost:8501`**
