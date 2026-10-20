"""Chronological retrospective evaluation of simple price/volatility baselines."""
from __future__ import annotations
import math
import pandas as pd


def evaluate_historical_ranges(history: pd.DataFrame) -> pd.DataFrame:
    """Evaluate monthly rolling origins using only observations before each origin.

    This is a diagnostic, not a fully point-in-time backtest: adjusted historical
    provider data can be revised after corporate actions and the symbol universe
    is selected by the user (survivorship bias).
    """
    if "Close" not in history or len(history) < 300:
        return pd.DataFrame()
    close = history["Close"].dropna().astype(float)
    if len(close) < 300:
        return pd.DataFrame()
    returns = close.pct_change()
    rows = []
    horizons = (("3 months", 63), ("6 months", 126), ("12 months", 252))
    # Monthly (21-session) origins; exclude origins without a full one-year past window.
    for horizon_name, horizon_sessions in horizons:
        errors, covered = [], []
        for origin in range(252, len(close) - horizon_sessions, 21):
            past_returns = returns.iloc[origin - 252:origin].dropna()
            if len(past_returns) < 200:
                continue
            sigma = float(past_returns.std() * math.sqrt(252))
            start = float(close.iloc[origin - 1])
            actual = float(close.iloc[origin + horizon_sessions - 1])
            actual_return = actual / start - 1
            errors.append(abs(actual_return))  # flat-price baseline predicts 0% return
            band = 1.645 * sigma * math.sqrt(horizon_sessions / 252)
            covered.append(-band <= actual_return <= band)
        if errors:
            rows.append({"Horizon": horizon_name, "Origins": len(errors),
                "Flat-baseline MAE (return %)": round(100 * sum(errors) / len(errors), 2),
                "Historical range coverage (%)": round(100 * sum(covered) / len(covered), 1)})
    return pd.DataFrame(rows)
