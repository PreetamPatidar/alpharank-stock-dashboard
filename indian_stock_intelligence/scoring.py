"""Transparent, deterministic screening scores for the research MVP."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

WEIGHTS = {
    "Business quality": 25,
    "Growth": 20,
    "Valuation": 20,
    "Momentum": 15,
    "Risk & stability": 15,
    "Events & sector context": 5,
}
MODEL_VERSION = "research-mvp-0.1"


def _num(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


@dataclass
class ScoreResult:
    score: float | None
    coverage: float
    components: list[dict[str, Any]]
    positives: list[str]
    negatives: list[str]
    missing: list[str]


def calculate_score(info: dict[str, Any], technical: dict[str, Any]) -> ScoreResult:
    """Score only observed categories; missing categories contribute zero and reduce coverage."""
    values: dict[str, tuple[float | None, str, str]] = {}

    roe = _num(info.get("returnOnEquity"))
    margins = _num(info.get("operatingMargins"))
    quality_inputs = [x for x in (roe, margins) if x is not None]
    if quality_inputs:
        parts = [max(0, min(100, (x * 100 / 30))) for x in (roe,) if x is not None]
        parts += [max(0, min(100, x * 100 / 20)) for x in (margins,) if x is not None]
        values["Business quality"] = (sum(parts) / len(parts), "ROE and operating margin", "Rewards stronger returns and margins; capped at 30% ROE and 20% margin.")

    growth = _num(info.get("revenueGrowth"))
    earnings_growth = _num(info.get("earningsGrowth"))
    growth_inputs = [x for x in (growth, earnings_growth) if x is not None]
    if growth_inputs:
        values["Growth"] = (sum(_clamp(50 + x * 125) for x in growth_inputs) / len(growth_inputs), "Revenue and earnings growth", "Growth maps from -40% (0 points) to +40% (100 points).")

    pe = _num(info.get("trailingPE"))
    if pe is not None and pe > 0:
        values["Valuation"] = (_clamp(100 - 35 * math.log2(max(pe, 1) / 15)), "Trailing P/E", "Screening reference is 15x earnings; negative earnings make P/E unavailable. Not sector-adjusted.")

    mom = technical.get("momentum_score")
    if mom is not None:
        values["Momentum"] = (float(mom), "20/50/200-day trend and 6-month return", "Moving-average alignment and historical return; descriptive, not predictive.")

    debt_equity = _num(info.get("debtToEquity"))
    beta = _num(info.get("beta"))
    risk_values = []
    if debt_equity is not None and debt_equity >= 0:
        de_ratio = debt_equity / 100 if debt_equity > 10 else debt_equity
        risk_values.append(_clamp(100 - de_ratio * 50))
    vol = technical.get("annualized_volatility")
    if vol is not None:
        risk_values.append(_clamp(100 - float(vol) * 100))
    if beta is not None and beta >= 0:
        risk_values.append(_clamp(100 - abs(beta - 1) * 35))
    if risk_values:
        values["Risk & stability"] = (sum(risk_values) / len(risk_values), "Debt/equity, annualized volatility and beta", "Higher leverage, volatility or beta away from 1 lowers this screening score.")

    components = []
    positives, negatives, missing = [], [], []
    observed_weight = 0
    total = 0.0
    for category, weight in WEIGHTS.items():
        if category not in values:
            missing.append(category)
            components.append({"Category": category, "Weight": f"{weight}%", "Score": None, "Contribution": 0.0, "Inputs": "Unavailable", "Explanation": "No usable input; no neutral value was substituted."})
            continue
        score, inputs, explanation = values[category]
        contribution = weight * score / 100
        total += contribution
        observed_weight += weight
        line = f"{category}: {score:.0f}/100"
        (positives if score >= 65 else negatives if score < 40 else []).append(line)
        components.append({"Category": category, "Weight": f"{weight}%", "Score": round(score, 1), "Contribution": round(contribution, 2), "Inputs": inputs, "Explanation": explanation})

    # No rescaling: a missing category does not inflate the total. Coverage is shown separately.
    return ScoreResult(round(total, 1) if observed_weight else None, round(observed_weight, 1), components, positives, negatives, missing)
