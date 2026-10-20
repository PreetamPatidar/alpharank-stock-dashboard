"""Unvalidated volatility scenarios: descriptive stress ranges, not predictions."""
import math
import pandas as pd


def scenarios(price: float, annualized_volatility: float | None) -> pd.DataFrame:
    sigma = max(0.0, float(annualized_volatility or 0.0))
    rows = []
    for months in (3, 6, 12):
        t = months / 12
        move = 1.645 * sigma * math.sqrt(t)
        for name, ret in (("Bearish", -move), ("Base (flat-price baseline)", 0.0), ("Bullish", move)):
            estimate = price * (1 + ret)
            rows.append({"Horizon": f"{months} months", "Scenario": name, "Estimated price": round(estimate, 2), "Change": f"{ret:+.1%}"})
    return pd.DataFrame(rows)
