"""Tests for qualitative analysis modules."""

import unittest
from src.qualitative.sentiment import SentimentAnalyzer
from src.qualitative.team_scoring import TeamScorer
from src.qualitative.vc_analysis import VCAnalyzer


class TestSentimentAnalyzer(unittest.TestCase):
    """Test sentiment analysis logic."""

    def setUp(self):
        self.analyzer = SentimentAnalyzer()

    def test_hype_index_range(self):
        """Test hype index is always 0-100."""
        community_data = {
            "community": {
                "twitter_followers": 500000,
                "reddit_subscribers": 100000,
                "reddit_accounts_active_48h": 5000,
                "telegram_channel_user_count": 50000,
            },
            "description": "A great blockchain project with amazing technology.",
        }
        result = self.analyzer.analyze(community_data, "TestToken")
        self.assertGreaterEqual(result.hype_index, 0)
        self.assertLessEqual(result.hype_index, 100)

    def test_organic_ratio_range(self):
        """Test organic ratio is 0-1."""
        result = self.analyzer.analyze({"community": {}, "description": ""}, "Test")
        self.assertGreaterEqual(result.organic_ratio, 0)
        self.assertLessEqual(result.organic_ratio, 1)

    def test_empty_data_handling(self):
        """Test handling of empty community data."""
        result = self.analyzer.analyze({}, "EmptyToken")
        self.assertEqual(result.social_volume_24h, 0)

    def test_score_in_range(self):
        """Test score is 0-100."""
        result = self.analyzer.analyze({"community": {}, "description": ""}, "Test")
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)


class TestTeamScorer(unittest.TestCase):
    """Test team scoring logic."""

    def setUp(self):
        self.scorer = TeamScorer()

    def test_known_founder_scoring(self):
        """Test scoring of known founders."""
        community_data = {
            "developer": {"commit_count_4_weeks": 100},
            "links": {"homepage": ["https://example.com"]},
        }
        result = self.scorer.analyze(
            community_data,
            known_founders=["Vitalik Buterin"],
        )
        self.assertTrue(result.founders_identified)
        self.assertTrue(result.founders_doxxed)
        self.assertGreater(result.team_score, 0)

    def test_unknown_team_low_score(self):
        """Test that unknown teams get lower scores."""
        result = self.scorer.analyze({"developer": {}, "links": {}})
        self.assertLess(result.team_score, 50)

    def test_dev_activity_scoring(self):
        """Test development activity scoring."""
        community_data = {
            "developer": {"commit_count_4_weeks": 200},
            "links": {},
        }
        result = self.scorer.analyze(community_data)
        self.assertGreater(result.development_activity_score, 0)


class TestVCAnalyzer(unittest.TestCase):
    """Test VC analysis logic."""

    def setUp(self):
        self.analyzer = VCAnalyzer()

    def test_tier1_classification(self):
        """Test Tier-1 VC identification."""
        result = self.analyzer.analyze(
            "TestToken",
            known_investors=["a16z", "Paradigm", "Polychain Capital"],
        )
        self.assertEqual(len(result.tier1_investors), 3)
        self.assertGreaterEqual(result.vc_reputation_score, 50)

    def test_unknown_investors_lower_score(self):
        """Test unknown investors get lower score."""
        result = self.analyzer.analyze(
            "TestToken",
            known_investors=["Unknown Fund 1", "Unknown Fund 2"],
        )
        self.assertLess(result.vc_reputation_score, 30)

    def test_no_investors(self):
        """Test with no investors."""
        result = self.analyzer.analyze("TestToken")
        self.assertEqual(result.vc_reputation_score, 0)

    def test_partnership_scoring(self):
        """Test partnership quality scoring."""
        result = self.analyzer.analyze(
            "TestToken",
            known_partners=["Google Cloud", "Microsoft"],
        )
        self.assertGreater(result.partnership_quality_score, 50)

    def test_score_in_range(self):
        """Test score is 0-100."""
        result = self.analyzer.analyze(
            "TestToken",
            known_investors=["a16z"],
        )
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)


if __name__ == "__main__":
    unittest.main()
