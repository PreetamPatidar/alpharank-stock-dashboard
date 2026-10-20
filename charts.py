"""
Interactive Plotly Visualizations for Stock Ranking Dashboard
"""

from typing import Dict, Any, List
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


# Color constants for score tiers
COLOR_STRONG = "#10B981"   # Emerald Green (> 70)
COLOR_NEUTRAL = "#F59E0B"  # Amber / Yellow (40 - 70)
COLOR_WEAK = "#EF4444"     # Crimson Red (< 40)
BG_DARK = "#0E1117"
BG_CARD = "#1A1F2C"
TEXT_COLOR = "#F3F4F6"
GRID_COLOR = "#2D3748"


def get_score_color(score: float) -> str:
    """Returns color based on score tier."""
    if score >= 70.0:
        return COLOR_STRONG
    elif score >= 40.0:
        return COLOR_NEUTRAL
    else:
        return COLOR_WEAK


def create_horizontal_ranking_chart(df: pd.DataFrame) -> go.Figure:
    """
    Creates a Plotly horizontal bar chart showing final Investment Scores of all compared stocks.
    Color-coded: Green for >70, Yellow for 40-70, Red for <40.
    """
    # Sort ascending for horizontal bar chart so highest is on top
    plot_df = df.sort_values(by="investment_score", ascending=True).copy()
    
    colors = [get_score_color(s) for s in plot_df["investment_score"]]
    
    hover_texts = [
        f"<b>{row['ticker']}</b> ({row['name']})<br>"
        f"Overall Score: <b>{row['investment_score']} / 100</b><br>"
        f"Rating: {row['rating']}<br>"
        f"• Efficiency (35%): {row['efficiency_score']}<br>"
        f"• Financial Risk (30%): {row['financial_risk_score']}<br>"
        f"• Valuation (25%): {row['valuation_score']}<br>"
        f"• Momentum (10%): {row['momentum_score']}"
        for _, row in plot_df.iterrows()
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=plot_df["ticker"],
        x=plot_df["investment_score"],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(color="rgba(255, 255, 255, 0.2)", width=1),
            cornerradius=4
        ),
        text=[f" <b>{s:.1f}</b>" for s in plot_df["investment_score"]],
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(color="#FFFFFF", size=13, family="Inter, Arial, sans-serif"),
        hoverinfo="text",
        hovertext=hover_texts,
    ))
    
    # Threshold indicator lines (40 and 70)
    fig.add_vline(
        x=70,
        line_width=1.5,
        line_dash="dash",
        line_color=COLOR_STRONG,
        annotation_text="Strong (>70)",
        annotation_position="top right",
        annotation_font=dict(color=COLOR_STRONG, size=11)
    )
    fig.add_vline(
        x=40,
        line_width=1.5,
        line_dash="dash",
        line_color=COLOR_NEUTRAL,
        annotation_text="Neutral (40)",
        annotation_position="bottom right",
        annotation_font=dict(color=COLOR_NEUTRAL, size=11)
    )
    
    fig.update_layout(
        title=dict(
            text="<b>Multi-Factor Investment Score Ranking</b>",
            font=dict(size=18, color=TEXT_COLOR)
        ),
        xaxis=dict(
            title="Composite Investment Score (0 - 100)",
            range=[0, 105],
            showgrid=True,
            gridcolor=GRID_COLOR,
            tickfont=dict(color="#9CA3AF"),
            title_font=dict(color="#D1D5DB")
        ),
        yaxis=dict(
            title="",
            tickfont=dict(color=TEXT_COLOR, size=13, family="monospace"),
            autorange=True,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=40, t=60, b=50),
        height=max(360, len(plot_df) * 45),
    )
    
    return fig


def create_factor_breakdown_radar(stock_row: pd.Series) -> go.Figure:
    """
    Creates a radar / spider chart showing how individual factors contributed
    to a selected stock's score.
    """
    categories = [
        "Efficiency<br>(ROE - 35%)",
        "Financial Risk<br>(D/E - 30%)",
        "Valuation<br>(P/E - 25%)",
        "Momentum<br>(SMA - 10%)"
    ]
    
    sub_scores = [
        stock_row["efficiency_score"],
        stock_row["financial_risk_score"],
        stock_row["valuation_score"],
        stock_row["momentum_score"]
    ]
    
    # Close the radar loop
    radar_cats = categories + [categories[0]]
    radar_scores = sub_scores + [sub_scores[0]]
    
    fig = go.Figure()
    
    # Target stock trace
    fig.add_trace(go.Scatterpolar(
        r=radar_scores,
        theta=radar_cats,
        fill="toself",
        fillcolor="rgba(16, 185, 129, 0.25)" if stock_row["investment_score"] >= 70 
                  else ("rgba(245, 158, 11, 0.25)" if stock_row["investment_score"] >= 40 
                        else "rgba(239, 68, 68, 0.25)"),
        line=dict(
            color=get_score_color(stock_row["investment_score"]),
            width=2.5
        ),
        name=stock_row["ticker"],
        hoverinfo="theta+r"
    ))
    
    # Benchmark 50 neutral ring
    fig.add_trace(go.Scatterpolar(
        r=[50, 50, 50, 50, 50],
        theta=radar_cats,
        mode="lines",
        line=dict(color="rgba(156, 163, 175, 0.4)", dash="dot", width=1.5),
        name="Baseline (50 pts)",
        hoverinfo="none"
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[20, 40, 60, 80, 100],
                tickfont=dict(color="#9CA3AF", size=10),
                gridcolor=GRID_COLOR,
                linecolor=GRID_COLOR
            ),
            angularaxis=dict(
                tickfont=dict(color=TEXT_COLOR, size=12),
                linecolor=GRID_COLOR,
                gridcolor=GRID_COLOR
            ),
            bgcolor="rgba(0,0,0,0)"
        ),
        title=dict(
            text=f"<b>Factor Sub-Scores Profile: {stock_row['ticker']}</b>",
            font=dict(size=16, color=TEXT_COLOR)
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(font=dict(color="#9CA3AF"), orientation="h", y=-0.15, x=0.2),
        margin=dict(l=60, r=60, t=50, b=40),
        height=380,
    )
    
    return fig


def create_factor_contribution_bar(stock_row: pd.Series, weights: Dict[str, float]) -> go.Figure:
    """
    Creates a horizontal waterfall/bar chart showing raw sub-scores and weighted contributions.
    """
    factors = ["Efficiency (35%)", "Financial Risk (30%)", "Valuation (25%)", "Momentum (10%)"]
    raw_scores = [
        stock_row["efficiency_score"],
        stock_row["financial_risk_score"],
        stock_row["valuation_score"],
        stock_row["momentum_score"]
    ]
    w_list = [weights["efficiency"], weights["financial_risk"], weights["valuation"], weights["momentum"]]
    weighted_contribs = [raw * w for raw, w in zip(raw_scores, w_list)]
    
    fig = go.Figure()
    
    # Sub-score trace (scale 0-100)
    fig.add_trace(go.Bar(
        name="Raw Sub-Score (0-100)",
        y=factors,
        x=raw_scores,
        orientation="h",
        marker=dict(color="#3B82F6", opacity=0.85, cornerradius=4),
        text=[f"{s:.1f}" for s in raw_scores],
        textposition="inside",
        textfont=dict(color="#FFFFFF", size=12)
    ))
    
    # Weighted contribution trace (points towards final score)
    fig.add_trace(go.Bar(
        name="Weighted Contribution to Total",
        y=factors,
        x=weighted_contribs,
        orientation="h",
        marker=dict(color="#10B981", opacity=0.85, cornerradius=4),
        text=[f"+{c:.1f} pts" for c in weighted_contribs],
        textposition="inside",
        textfont=dict(color="#FFFFFF", size=12)
    ))
    
    fig.update_layout(
        barmode="group",
        title=dict(
            text=f"<b>Factor Contribution Breakdown for {stock_row['ticker']}</b>",
            font=dict(size=16, color=TEXT_COLOR)
        ),
        xaxis=dict(
            title="Score Points",
            range=[0, 105],
            showgrid=True,
            gridcolor=GRID_COLOR,
            tickfont=dict(color="#9CA3AF")
        ),
        yaxis=dict(tickfont=dict(color=TEXT_COLOR, size=12)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(font=dict(color="#D1D5DB"), orientation="h", y=1.12, x=0),
        margin=dict(l=60, r=40, t=70, b=40),
        height=340,
    )
    
    return fig


def create_price_sma_chart(ticker: str, hist: pd.DataFrame, sma50_val: float, sma200_val: float) -> go.Figure:
    """
    Creates an interactive 1-year Price chart with 50-day and 200-day Simple Moving Averages.
    """
    if hist.empty:
        return go.Figure()
        
    df = hist.copy()
    if "Close" not in df.columns:
        return go.Figure()
        
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()
    
    fig = go.Figure()
    
    # Close price line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"],
        mode="lines",
        name=f"{ticker} Price",
        line=dict(color="#60A5FA", width=2),
        hoverinfo="x+y"
    ))
    
    # 50 SMA line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["SMA50"],
        mode="lines",
        name="50-Day SMA",
        line=dict(color="#F59E0B", width=1.8, dash="solid")
    ))
    
    # 200 SMA line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["SMA200"],
        mode="lines",
        name="200-Day SMA",
        line=dict(color="#EC4899", width=1.8, dash="solid")
    ))
    
    curr_price = df["Close"].iloc[-1]
    
    # Momentum status tag
    status_text = "Golden Trend (Price > 50 SMA > 200 SMA)" if (curr_price > sma50_val > sma200_val) else "Non-ideal SMA alignment"
    status_color = COLOR_STRONG if (curr_price > sma50_val > sma200_val) else COLOR_NEUTRAL
    
    curr_sym = "₹" if (".NS" in ticker or ".BO" in ticker) else "$"
    fig.update_layout(
        title=dict(
            text=f"<b>{ticker} 1-Year Historical Price vs 50 & 200 SMA</b> <span style='font-size:13px; color:{status_color}'>({status_text})</span>",
            font=dict(size=15, color=TEXT_COLOR)
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor=GRID_COLOR,
            tickfont=dict(color="#9CA3AF"),
        ),
        yaxis=dict(
            title=f"Price ({curr_sym})",
            showgrid=True,
            gridcolor=GRID_COLOR,
            tickfont=dict(color="#9CA3AF")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(font=dict(color="#D1D5DB"), orientation="h", y=1.1, x=0),
        margin=dict(l=50, r=30, t=60, b=40),
        height=360,
        hovermode="x unified"
    )
    
    return fig


def create_all_stocks_factor_comparison(df: pd.DataFrame) -> go.Figure:
    """
    Stacked or grouped bar chart comparing all stocks across the 4 factors.
    """
    fig = go.Figure()
    
    factors = [
        ("Efficiency (35%)", "efficiency_score", "#3B82F6"),
        ("Financial Risk (30%)", "financial_risk_score", "#10B981"),
        ("Valuation (25%)", "valuation_score", "#8B5CF6"),
        ("Momentum (10%)", "momentum_score", "#F59E0B"),
    ]
    
    for label, col, color in factors:
        fig.add_trace(go.Bar(
            name=label,
            x=df["ticker"],
            y=df[col],
            marker=dict(color=color, cornerradius=3),
            text=[f"{v:.0f}" for v in df[col]],
            textposition="auto",
            textfont=dict(size=11)
        ))
        
    fig.update_layout(
        barmode="group",
        title=dict(
            text="<b>Cross-Factor Comparison Across All Tickers</b>",
            font=dict(size=16, color=TEXT_COLOR)
        ),
        xaxis=dict(tickfont=dict(color=TEXT_COLOR, size=12)),
        yaxis=dict(
            title="Sub-Score (0 - 100)",
            range=[0, 105],
            showgrid=True,
            gridcolor=GRID_COLOR,
            tickfont=dict(color="#9CA3AF")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(font=dict(color="#D1D5DB"), orientation="h", y=1.12, x=0),
        margin=dict(l=50, r=30, t=70, b=40),
        height=380,
    )
    
    return fig
