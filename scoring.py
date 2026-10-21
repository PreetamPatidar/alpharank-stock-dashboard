"""
Multi-factor Scoring Engine for Stocks
Calculates normalized scores (0-100) across 4 key financial dimensions:
1. Efficiency (35%): Return on Equity (ROE) - Higher is better, negative is penalized.
2. Financial Risk (30%): Debt-to-Equity (D/E) - Lower is better. Zero debt = 100, D/E > 2 = 0.
3. Valuation (25%): Trailing P/E compared to batch median. Lower relative P/E ranks higher.
4. Momentum (10%): Price vs 50-day and 200-day SMA. Maximum when Price > 50 SMA > 200 SMA.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd


WEIGHTS = {
    "efficiency": 0.35,
    "financial_risk": 0.30,
    "valuation": 0.25,
    "momentum": 0.10,
}


def calculate_efficiency_score(roe_series: pd.Series) -> pd.Series:
    """
    Efficiency (35% Weight):
    Higher ROE gives a higher sub-score.
    Penalize if ROE is negative (assigned 0).
    For positive ROE, scales smoothly based on batch relative performance with benchmark floor/ceiling.
    """
    scores = pd.Series(index=roe_series.index, dtype=float)
    
    # Handle NaN or missing
    valid_roe = roe_series.dropna()
    
    for idx, val in roe_series.items():
        if pd.isna(val):
            scores[idx] = 0.0
        elif val <= 0:
            # Negative or zero ROE is penalized
            scores[idx] = 0.0
        else:
            # val is positive ROE (e.g. 0.25 for 25% or 25 if expressed as %)
            # Ensure roe in percentage form for consistent benchmark
            roe_pct = val * 100.0 if val < 2.0 else val
            
            # Benchmark baseline: 0% -> 0, 30%+ -> 100 (superb capital efficiency)
            # We also blend with relative batch percentile rank for crisp separation
            pos_vals = [v * 100.0 if v < 2.0 else v for v in valid_roe if v > 0]
            if len(pos_vals) > 1 and max(pos_vals) > min(pos_vals):
                min_v, max_v = min(pos_vals), max(pos_vals)
                rel_score = 20.0 + 80.0 * ((roe_pct - min_v) / (max_v - min_v))
            else:
                rel_score = min(100.0, max(10.0, (roe_pct / 30.0) * 100.0))
                
            abs_score = min(100.0, max(0.0, (roe_pct / 30.0) * 100.0))
            # Balanced blend of relative peer ranking and absolute financial quality
            final_sub = 0.5 * rel_score + 0.5 * abs_score
            scores[idx] = round(float(np.clip(final_sub, 0.0, 100.0)), 1)
            
    return scores


def calculate_financial_risk_score(de_series: pd.Series) -> pd.Series:
    """
    Financial Risk (30% Weight):
    Lower Debt-to-Equity gives a higher sub-score.
    Zero debt gets maximum points (100).
    D/E > 2 gets 0 points for this factor.
    Scales linearly between 0 and 2.
    """
    scores = pd.Series(index=de_series.index, dtype=float)
    
    for idx, val in de_series.items():
        if pd.isna(val):
            scores[idx] = 50.0  # Neutral baseline for companies without reported debt
            continue
            
        # yfinance often returns debtToEquity as e.g. 150 (meaning 1.5x) or 1.5
        de = float(val)
        if de > 10.0:  # standard yfinance percentage representation (e.g. 120 -> 1.20)
            de = de / 100.0
            
        if de <= 0.0:
            scores[idx] = 100.0
        elif de >= 2.0:
            scores[idx] = 0.0
        else:
            # Linear decay from 100 at 0 to 0 at 2.0
            score = 100.0 * (2.0 - de) / 2.0
            scores[idx] = round(float(np.clip(score, 0.0, 100.0)), 1)
            
    return scores


def calculate_valuation_score(pe_series: pd.Series) -> pd.Series:
    """
    Valuation (25% Weight):
    Compare the stock's P/E to the median P/E of the imported batch.
    A lower relative P/E score ranks higher.
    Unprofitable stocks (P/E <= 0) receive 0 points; missing receive neutral 30.
    """
    scores = pd.Series(index=pe_series.index, dtype=float)
    
    # Filter positive P/E for batch median calculation
    positive_pes = pe_series[(pe_series.notna()) & (pe_series > 0)]
    
    if len(positive_pes) == 0:
        # No valid positive P/Es in batch
        scores[:] = 0.0
        return scores
        
    median_pe = positive_pes.median()
    
    for idx, val in pe_series.items():
        if pd.isna(val):
            scores[idx] = 30.0  # Neutral-conservative baseline for missing P/E
        elif val <= 0:
            scores[idx] = 0.0   # Negative P/E (Loss-making) penalized
        else:
            ratio = val / median_pe
            if ratio <= 1.0:
                # Cheaper than median: ranges from 50 (at median) up to 100 (when approaching 0)
                sub_score = 50.0 + 50.0 * (1.0 - ratio)
            else:
                # More expensive than median: drops from 50 (at median) down to 0 (at 2x median or higher)
                sub_score = max(0.0, 50.0 - 50.0 * (ratio - 1.0))
                
            scores[idx] = round(float(np.clip(sub_score, 0.0, 100.0)), 1)
            
    return scores


def calculate_momentum_score(
    price_series: pd.Series,
    sma_50_series: pd.Series,
    sma_200_series: pd.Series
) -> pd.Series:
    """
    Momentum (10% Weight):
    If current price > 50-day SMA > 200-day SMA, award maximum points (100);
    otherwise scale lower depending on moving average alignment.
    """
    scores = pd.Series(index=price_series.index, dtype=float)
    
    for idx in price_series.index:
        p = price_series.get(idx)
        s50 = sma_50_series.get(idx)
        s200 = sma_200_series.get(idx)
        
        if pd.isna(p) or pd.isna(s50) or pd.isna(s200):
            scores[idx] = 0.0
            continue
            
        p, s50, s200 = float(p), float(s50), float(s200)
        
        # Primary condition: Strong Bullish alignment
        if p > s50 and s50 > s200:
            # Price > 50-day SMA > 200-day SMA
            sub_score = 100.0
        elif p > s50 and p > s200 and s50 <= s200:
            # Bullish price above both, 50 SMA recovering
            sub_score = 75.0
        elif s50 > s200 and p <= s50 and p > s200:
            # Healthy pullback: above 200 SMA while golden cross intact
            sub_score = 60.0
        elif p > s200 and p <= s50:
            # Above long term trend only
            sub_score = 45.0
        elif p > s50 and p <= s200:
            # Short term bounce beneath 200 SMA
            sub_score = 30.0
        elif p <= s50 and s50 > s200 and p <= s200:
            # Break below both MAs during lag
            sub_score = 15.0
        else:
            # Bearish alignment: Price < 50 SMA < 200 SMA or death cross
            sub_score = 5.0
            
        scores[idx] = round(sub_score, 1)
        
    return scores


def calculate_multi_factor_rankings(
    df: pd.DataFrame,
    custom_weights: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Calculates sub-scores and overall normalized Investment Score (0-100)
    for a dataframe containing ticker metrics.
    
    Expected columns in df:
    - 'ticker'
    - 'currentPrice'
    - 'returnOnEquity'
    - 'debtToEquity'
    - 'trailingPE'
    - 'sma50'
    - 'sma200'
    """
    result = df.copy()
    
    # Resolve active weights normalized to 1.0
    w = WEIGHTS.copy()
    if custom_weights:
        tot = sum(custom_weights.values())
        if tot > 0:
            w = {k: v / tot for k, v in custom_weights.items()}
            
    # 1. Efficiency Sub-Score
    result["efficiency_score"] = calculate_efficiency_score(result["returnOnEquity"])
    
    # 2. Financial Risk Sub-Score
    result["financial_risk_score"] = calculate_financial_risk_score(result["debtToEquity"])
    
    # 3. Valuation Sub-Score
    result["valuation_score"] = calculate_valuation_score(result["trailingPE"])
    
    # 4. Momentum Sub-Score
    result["momentum_score"] = calculate_momentum_score(
        result["currentPrice"],
        result["sma50"],
        result["sma200"]
    )
    
    # 5. Composite Investment Score (0 to 100)
    result["investment_score"] = (
        result["efficiency_score"] * w.get("efficiency", 0.35) +
        result["financial_risk_score"] * w.get("financial_risk", 0.30) +
        result["valuation_score"] * w.get("valuation", 0.25) +
        result["momentum_score"] * w.get("momentum", 0.10)
    ).round(1)
    
    # Rank assignment
    result["rank"] = result["investment_score"].rank(ascending=False, method="min").astype(int)
    
    # Sort from highest to lowest score
    result = result.sort_values(by=["investment_score", "rank"], ascending=[False, True]).reset_index(drop=True)
    
    # Rating category
    def assign_category(score: float) -> str:
        if score >= 70.0:
            return "Strong Buy / Outperform"
        elif score >= 40.0:
            return "Hold / Neutral"
        else:
            return "Underperform / High Risk"
            
    result["rating"] = result["investment_score"].apply(assign_category)
    
    return result
