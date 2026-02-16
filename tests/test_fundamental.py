"""Tests for fundamental tokenomics analysis."""

import unittest
from src.models.schemas import (
    TokenMarketData,
    TokenType,
    DistributionData,
    VestingSchedule,
)
from src.fundamental.tokenomics import TokenomicsAnalyzer


class TestTokenomicsAnalyzer(unittest.TestCase):
    """Test tokenomics analysis logic."""

    def setUp(self):
        self.analyzer = TokenomicsAnalyzer()
        self.sample_token = TokenMarketData(
            name="TestToken",
            symbol="TEST",
            token_type=TokenType.L1,
            price_usd=100.0,
            market_cap=1_000_000_000,
            fully_diluted_valuation=2_000_000_000,
            circulating_supply=10_000_000,
            total_supply=20_000_000,
            max_supply=20_000_000,
            volume_24h=50_000_000,
        )
        self.community_data = {
            "description": "A layer 1 blockchain with staking and governance features",
            "categories": ["Smart Contract Platform", "Layer 1"],
        }

    def test_inflation_calculation(self):
        """Test max inflation is calculated correctly."""
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        # (20M - 10M) / 10M * 100 = 100%
        self.assertEqual(result.inflation.max_inflation, 100.0)

    def test_fdv_ratio(self):
        """Test FDV/MCap ratio."""
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        self.assertEqual(result.fdv_mcap_ratio, 2.0)

    def test_supply_ratio(self):
        """Test supply ratio calculation."""
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        self.assertEqual(result.inflation.supply_ratio, 0.5)

    def test_l1_gets_pu_ratio(self):
        """Test that L1 tokens get PU ratio."""
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        self.assertIsNotNone(result.pu_ratio)

    def test_defi_no_pu_ratio(self):
        """Test that DeFi tokens don't get PU ratio."""
        self.sample_token.token_type = TokenType.DEFI
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        self.assertIsNone(result.pu_ratio)

    def test_custom_distribution_override(self):
        """Test distribution override."""
        custom_dist = DistributionData(
            team_allocation=10.0,
            investor_allocation=10.0,
            community_allocation=60.0,
            insider_percentage=20.0,
            community_percentage=60.0,
            data_available=True,
        )
        result = self.analyzer.analyze(
            self.sample_token, self.community_data,
            distribution_override=custom_dist,
        )
        self.assertEqual(result.distribution.insider_percentage, 20.0)
        self.assertTrue(result.distribution.data_available)

    def test_score_in_range(self):
        """Test score is always 0-100."""
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)

    def test_risk_signals_generated(self):
        """Test that risk signals are generated."""
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        self.assertGreater(len(result.risk_signals), 0)

    def test_high_fdv_generates_red_flag(self):
        """Test high FDV ratio generates a red flag."""
        self.sample_token.fully_diluted_valuation = 15_000_000_000  # 15x MCap
        result = self.analyzer.analyze(self.sample_token, self.community_data)
        red_flags = [f for f in result.risk_signals if f.signal.value == "ROJO"]
        fdv_flags = [f for f in red_flags if "FDV" in f.category]
        self.assertGreater(len(fdv_flags), 0)


class TestInflationMetrics(unittest.TestCase):
    """Test inflation-specific calculations."""

    def setUp(self):
        self.analyzer = TokenomicsAnalyzer()

    def test_zero_supply_handling(self):
        """Test handling of zero supply."""
        token = TokenMarketData(
            name="Zero",
            symbol="ZERO",
            circulating_supply=0,
            total_supply=0,
        )
        result = self.analyzer.analyze(token, {})
        self.assertEqual(result.inflation.max_inflation, 0.0)

    def test_fully_distributed(self):
        """Test fully distributed token (no inflation)."""
        token = TokenMarketData(
            name="Full",
            symbol="FULL",
            token_type=TokenType.L1,
            price_usd=1.0,
            market_cap=1000,
            circulating_supply=1000,
            total_supply=1000,
            max_supply=1000,
            volume_24h=100,
        )
        result = self.analyzer.analyze(token, {})
        self.assertEqual(result.inflation.max_inflation, 0.0)
        self.assertEqual(result.inflation.supply_ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
