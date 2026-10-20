"""
Unit tests for the Multi-Factor Scoring Engine
"""

import unittest
import pandas as pd
import numpy as np
from scoring import (
    calculate_efficiency_score,
    calculate_financial_risk_score,
    calculate_valuation_score,
    calculate_momentum_score,
    calculate_multi_factor_rankings,
)


class TestScoringEngine(unittest.TestCase):

    def test_efficiency_penalty_for_negative_roe(self):
        roe_series = pd.Series([-0.15, -0.01, 0.0, 0.25, 0.35], index=["A", "B", "C", "D", "E"])
        scores = calculate_efficiency_score(roe_series)
        
        # Negative and zero ROE must receive 0 points (penalized)
        self.assertEqual(scores["A"], 0.0)
        self.assertEqual(scores["B"], 0.0)
        self.assertEqual(scores["C"], 0.0)
        # Positive ROEs must receive positive scores
        self.assertGreater(scores["D"], 0.0)
        self.assertGreater(scores["E"], scores["D"])

    def test_financial_risk_debt_to_equity(self):
        # 0 debt -> 100 max points
        # 1.0 -> 50 points
        # >= 2.0 -> 0 points
        de_series = pd.Series([0.0, 1.0, 2.0, 3.5, 0.5], index=["ZERO", "ONE", "TWO", "THREE", "HALF"])
        scores = calculate_financial_risk_score(de_series)
        
        self.assertEqual(scores["ZERO"], 100.0)
        self.assertAlmostEqual(scores["ONE"], 50.0, places=1)
        self.assertEqual(scores["TWO"], 0.0)
        self.assertEqual(scores["THREE"], 0.0)
        self.assertAlmostEqual(scores["HALF"], 75.0, places=1)

    def test_financial_risk_percentage_input(self):
        # In yfinance, 150 often means 1.5 ratio, 50 means 0.5
        de_series = pd.Series([0, 50.0, 150.0, 250.0], index=["A", "B", "C", "D"])
        scores = calculate_financial_risk_score(de_series)
        self.assertEqual(scores["A"], 100.0)
        self.assertAlmostEqual(scores["B"], 75.0, places=1)
        self.assertAlmostEqual(scores["C"], 25.0, places=1)
        self.assertEqual(scores["D"], 0.0)

    def test_valuation_pe_relative_to_median(self):
        # Median of [10, 20, 30] is 20
        pe_series = pd.Series([10.0, 20.0, 40.0, -5.0], index=["CHEAP", "MEDIAN", "EXPENSIVE", "LOSS"])
        scores = calculate_valuation_score(pe_series)
        
        # Loss maker -> 0
        self.assertEqual(scores["LOSS"], 0.0)
        # At median -> 50 points
        self.assertAlmostEqual(scores["MEDIAN"], 50.0, places=1)
        # Cheaper than median -> higher than 50
        self.assertGreater(scores["CHEAP"], 50.0)
        # 2x median (40 vs 20) -> 0 points
        self.assertEqual(scores["EXPENSIVE"], 0.0)

    def test_momentum_moving_averages(self):
        # Case 1: Current Price > 50 SMA > 200 SMA -> 100 points
        p = pd.Series([150.0, 100.0], index=["BULLISH", "BEARISH"])
        s50 = pd.Series([140.0, 110.0], index=["BULLISH", "BEARISH"])
        s200 = pd.Series([120.0, 130.0], index=["BULLISH", "BEARISH"])
        
        scores = calculate_momentum_score(p, s50, s200)
        self.assertEqual(scores["BULLISH"], 100.0)
        self.assertLess(scores["BEARISH"], 20.0)

    def test_composite_ranking(self):
        df = pd.DataFrame([
            {
                "ticker": "HIGH_QUALITY",
                "name": "High Quality Corp",
                "currentPrice": 200.0,
                "returnOnEquity": 0.30,
                "debtToEquity": 0.2,
                "trailingPE": 15.0,
                "sma50": 190.0,
                "sma200": 170.0,
            },
            {
                "ticker": "POOR_QUALITY",
                "name": "Distressed Corp",
                "currentPrice": 20.0,
                "returnOnEquity": -0.10,
                "debtToEquity": 4.5,
                "trailingPE": -2.0,
                "sma50": 25.0,
                "sma200": 30.0,
            }
        ])
        
        result = calculate_multi_factor_rankings(df)
        self.assertEqual(result.iloc[0]["ticker"], "HIGH_QUALITY")
        self.assertEqual(result.iloc[1]["ticker"], "POOR_QUALITY")
        self.assertGreater(result.iloc[0]["investment_score"], 70.0)
        self.assertLess(result.iloc[1]["investment_score"], 20.0)


if __name__ == "__main__":
    unittest.main()
