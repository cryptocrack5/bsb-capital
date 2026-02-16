"""Tests for technical analysis modules."""

import unittest
import numpy as np
import pandas as pd
from src.technical.indicators import TechnicalIndicatorEngine
from src.technical.volatility import VolatilityEngine
from src.technical.news_impact import NewsImpactAnalyzer
from src.models.schemas import TrendDirection, VolatilityRegime


class TestTechnicalIndicators(unittest.TestCase):
    """Test technical indicator calculations."""

    def setUp(self):
        self.engine = TechnicalIndicatorEngine()
        # Generate sample OHLCV data (uptrend)
        np.random.seed(42)
        n = 300
        prices = 100 + np.cumsum(np.random.randn(n) * 0.5 + 0.05)
        self.df = pd.DataFrame({
            "open": prices - np.random.rand(n) * 0.5,
            "high": prices + np.abs(np.random.randn(n)),
            "low": prices - np.abs(np.random.randn(n)),
            "close": prices,
            "volume": np.random.randint(1000, 10000, n).astype(float),
        }, index=pd.date_range("2024-01-01", periods=n, freq="D"))

    def test_rsi_range(self):
        """Test RSI is always 0-100."""
        result = self.engine.analyze(self.df)
        self.assertGreaterEqual(result.rsi, 0)
        self.assertLessEqual(result.rsi, 100)

    def test_bollinger_bandwidth_positive(self):
        """Test Bollinger bandwidth is non-negative."""
        result = self.engine.analyze(self.df)
        self.assertGreaterEqual(result.bb_bandwidth, 0)

    def test_moving_averages_computed(self):
        """Test moving averages are computed."""
        result = self.engine.analyze(self.df)
        self.assertGreater(result.ma_20, 0)
        self.assertGreater(result.ma_50, 0)
        self.assertGreater(result.ma_200, 0)

    def test_vwap_computed(self):
        """Test VWAP is computed when volume available."""
        result = self.engine.analyze(self.df)
        self.assertGreater(result.vwap, 0)

    def test_score_in_range(self):
        """Test momentum score is 0-100."""
        result = self.engine.analyze(self.df)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        short_df = self.df.iloc[:10]
        result = self.engine.analyze(short_df)
        # Should return defaults without error (score defaults to 50)
        self.assertEqual(result.score, 50.0)


class TestVolatilityEngine(unittest.TestCase):
    """Test volatility analysis."""

    def setUp(self):
        self.engine = VolatilityEngine()
        np.random.seed(42)
        n = 300
        prices = 100 + np.cumsum(np.random.randn(n) * 2)
        self.df = pd.DataFrame({
            "open": prices - np.random.rand(n),
            "high": prices + np.abs(np.random.randn(n) * 2),
            "low": prices - np.abs(np.random.randn(n) * 2),
            "close": prices,
        }, index=pd.date_range("2024-01-01", periods=n, freq="D"))

    def test_atr_positive(self):
        """Test ATR is positive."""
        result = self.engine.analyze(self.df)
        self.assertGreater(result.atr, 0)

    def test_historical_volatility_positive(self):
        """Test HV is positive."""
        result = self.engine.analyze(self.df)
        self.assertGreater(result.historical_volatility_30d, 0)

    def test_max_drawdown_negative(self):
        """Test max drawdown is non-positive."""
        result = self.engine.analyze(self.df)
        self.assertLessEqual(result.max_drawdown_30d, 0)

    def test_confidence_range(self):
        """Test confidence is 0.1-1.0."""
        result = self.engine.analyze(self.df)
        self.assertGreaterEqual(result.confidence_adjustment, 0.1)
        self.assertLessEqual(result.confidence_adjustment, 1.0)

    def test_choppiness_range(self):
        """Test choppiness index range."""
        result = self.engine.analyze(self.df)
        self.assertGreaterEqual(result.choppiness_index, 0)
        self.assertLessEqual(result.choppiness_index, 100)

    def test_regime_detection(self):
        """Test regime is a valid enum."""
        result = self.engine.analyze(self.df)
        self.assertIsInstance(result.market_regime, VolatilityRegime)


class TestNewsImpactAnalyzer(unittest.TestCase):
    """Test news impact analysis."""

    def setUp(self):
        self.analyzer = NewsImpactAnalyzer()

    def test_positive_description_sentiment(self):
        """Test positive description yields positive sentiment."""
        result = self.analyzer.analyze(
            "TestToken",
            description="Amazing partnership with Google, huge adoption and growth milestone",
        )
        self.assertGreater(result.recent_news_sentiment, 0)

    def test_negative_description_sentiment(self):
        """Test negative description yields negative sentiment."""
        result = self.analyzer.analyze(
            "TestToken",
            description="Major hack exploit, SEC lawsuit investigation, project crash and ban",
        )
        self.assertLess(result.recent_news_sentiment, 0)

    def test_regulatory_risk_detection(self):
        """Test regulatory risk detection."""
        result = self.analyzer.analyze(
            "TestToken",
            description="SEC investigation and regulation compliance issues",
        )
        self.assertGreater(result.regulatory_risk, 0)

    def test_unlock_risk(self):
        """Test token unlock risk detection."""
        result = self.analyzer.analyze(
            "TestToken",
            has_upcoming_unlocks=True,
            inflation_rate=80.0,
        )
        self.assertGreater(len(result.upcoming_unlocks), 0)

    def test_score_in_range(self):
        """Test score is 0-100."""
        result = self.analyzer.analyze("TestToken")
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)


if __name__ == "__main__":
    unittest.main()
