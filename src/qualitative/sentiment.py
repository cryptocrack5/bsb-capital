"""
BSB Capital - Sentiment Analysis Module
Quantifies market hype, social momentum, and organic engagement.

Methodology based on:
- LunarCrush Galaxy Score framework
- NLP-based social sentiment aggregation (VADER)
- Organic vs. Bot engagement ratio estimation
- Social Volume vs. Price Action correlation
"""

import logging
import math
from typing import Optional

from config.settings import SENTIMENT_WEIGHTS
from src.models.schemas import SentimentAnalysis

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    Quantifies market sentiment using multi-source NLP and engagement metrics.

    The Hype Index is computed as:
        HI = w1*SV_norm + w2*SS + w3*ER + w4*OR + w5*MD

    Where:
        SV_norm = Normalized social volume (0-1)
        SS = Aggregate sentiment score (0-1)
        ER = Engagement rate (0-1)
        OR = Organic ratio estimate (0-1)
        MD = Momentum delta (0-1)
    """

    def __init__(self):
        self._vader = None

    def _get_vader(self):
        """Lazy-load VADER sentiment analyzer."""
        if self._vader is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                self._vader = SentimentIntensityAnalyzer()
            except ImportError:
                logger.warning("vaderSentiment not installed, using fallback")
                self._vader = None
        return self._vader

    def analyze(
        self,
        community_data: dict,
        token_name: str,
        price_change_7d: float = 0.0,
        volume_change_ratio: float = 1.0,
    ) -> SentimentAnalysis:
        """Run sentiment analysis on available data."""
        result = SentimentAnalysis()

        community = community_data.get("community", {})
        description = community_data.get("description", "")

        # Social volume from available sources
        twitter_followers = community.get("twitter_followers", 0) or 0
        reddit_subscribers = community.get("reddit_subscribers", 0) or 0
        reddit_active = community.get("reddit_accounts_active_48h", 0) or 0
        telegram_members = community.get("telegram_channel_user_count", 0) or 0

        total_social = twitter_followers + reddit_subscribers + telegram_members
        result.social_volume_24h = total_social

        # Sentiment from description using VADER
        vader = self._get_vader()
        if vader and description:
            scores = vader.polarity_scores(description)
            result.overall_sentiment = scores["compound"]

        # Platform-specific sentiment estimates
        result.twitter_sentiment = self._estimate_twitter_sentiment(
            twitter_followers, price_change_7d
        )
        result.reddit_sentiment = self._estimate_reddit_sentiment(
            reddit_subscribers, reddit_active
        )

        # Engagement rate
        result.engagement_rate = self._calculate_engagement_rate(
            twitter_followers, reddit_active, reddit_subscribers, telegram_members
        )

        # Organic ratio estimation
        result.organic_ratio = self._estimate_organic_ratio(
            total_social, result.engagement_rate, volume_change_ratio
        )

        # Social volume trend
        result.social_volume_trend = self._assess_volume_trend(volume_change_ratio)

        # Compute Hype Index (0-100)
        result.hype_index = self._compute_hype_index(result)

        # Final score
        result.score = self._compute_score(result, price_change_7d)

        return result

    def analyze_text_sentiment(self, texts: list[str]) -> float:
        """Analyze sentiment of a list of text strings. Returns -1 to 1."""
        vader = self._get_vader()
        if not vader or not texts:
            return 0.0

        scores = [vader.polarity_scores(text)["compound"] for text in texts]
        return sum(scores) / len(scores) if scores else 0.0

    def _estimate_twitter_sentiment(
        self, followers: int, price_change_7d: float
    ) -> float:
        """
        Estimate Twitter sentiment based on follower count and price action.
        In crypto, social sentiment tends to follow price (reflexivity).
        """
        base = 0.0

        # Price action correlation (behavioral finance reflexivity)
        if price_change_7d > 20:
            base = 0.7
        elif price_change_7d > 5:
            base = 0.4
        elif price_change_7d > -5:
            base = 0.1
        elif price_change_7d > -20:
            base = -0.3
        else:
            base = -0.6

        # Follower count adds stability (larger communities are less volatile)
        if followers > 1_000_000:
            stability = 0.1
        elif followers > 100_000:
            stability = 0.05
        else:
            stability = 0.0

        return max(-1.0, min(1.0, base + stability))

    def _estimate_reddit_sentiment(
        self, subscribers: int, active_48h: int
    ) -> float:
        """Estimate Reddit sentiment from activity ratio."""
        if subscribers == 0:
            return 0.0
        activity_ratio = active_48h / subscribers if subscribers > 0 else 0
        # High activity ratio suggests excitement (positive or negative)
        # Typical healthy ratio is 0.5-2%
        if activity_ratio > 0.05:
            return 0.5  # Very high activity = hype
        if activity_ratio > 0.02:
            return 0.3
        if activity_ratio > 0.005:
            return 0.1
        return -0.1  # Very low activity = disinterest

    def _calculate_engagement_rate(
        self,
        twitter_followers: int,
        reddit_active: int,
        reddit_subscribers: int,
        telegram_members: int,
    ) -> float:
        """
        Calculate normalized engagement rate (0-1).
        Based on active users vs. total followers ratio.
        """
        total = twitter_followers + reddit_subscribers + telegram_members
        if total == 0:
            return 0.0

        # Reddit active is our best proxy for engagement
        active_ratio = reddit_active / total if total > 0 else 0
        # Normalize to 0-1 scale (typical engagement is 0.1-5%)
        normalized = min(1.0, active_ratio / 0.05)
        return round(normalized, 3)

    def _estimate_organic_ratio(
        self,
        total_social: int,
        engagement_rate: float,
        volume_change_ratio: float,
    ) -> float:
        """
        Estimate the ratio of organic vs. bot/paid engagement.

        Signals of inorganic growth:
        - Very high social volume with very low engagement = bot followers
        - Social growth much faster than volume growth = paid marketing
        """
        organic = 0.5  # Start neutral

        # High engagement suggests organic community
        if engagement_rate > 0.5:
            organic += 0.2
        elif engagement_rate > 0.2:
            organic += 0.1
        elif engagement_rate < 0.05:
            organic -= 0.2  # Low engagement = likely bots

        # Volume correlation
        if 0.8 < volume_change_ratio < 1.5:
            organic += 0.1  # Stable volume = organic
        elif volume_change_ratio > 3.0:
            organic -= 0.1  # Sudden volume spike = possible manipulation

        # Size normalization (very large communities tend to be more organic)
        if total_social > 500_000:
            organic += 0.1
        elif total_social < 10_000:
            organic -= 0.1

        return max(0.0, min(1.0, organic))

    def _assess_volume_trend(self, volume_change_ratio: float) -> str:
        """Assess social volume trend."""
        if volume_change_ratio > 1.3:
            return "increasing"
        if volume_change_ratio < 0.7:
            return "decreasing"
        return "stable"

    def _compute_hype_index(self, analysis: SentimentAnalysis) -> float:
        """
        Compute Hype Index (0-100).

        HI = 100 * (w1*SV_norm + w2*SS + w3*ER + w4*OR + w5*MD)

        Uses weighted composite of normalized metrics.
        """
        w = SENTIMENT_WEIGHTS

        # Normalize social volume (log scale, 0-1)
        sv_norm = min(1.0, math.log1p(analysis.social_volume_24h) / math.log1p(10_000_000))

        # Sentiment score normalized to 0-1
        ss = (analysis.overall_sentiment + 1) / 2

        # Engagement rate already 0-1
        er = analysis.engagement_rate

        # Organic ratio already 0-1
        org = analysis.organic_ratio

        # Momentum delta from trend
        if analysis.social_volume_trend == "increasing":
            md = 0.8
        elif analysis.social_volume_trend == "stable":
            md = 0.5
        else:
            md = 0.2

        hype = 100 * (
            w["social_volume"] * sv_norm
            + w["sentiment_score"] * ss
            + w["engagement_rate"] * er
            + w["organic_ratio"] * org
            + w["momentum_delta"] * md
        )

        return round(max(0, min(100, hype)), 1)

    def _compute_score(
        self, analysis: SentimentAnalysis, price_change_7d: float
    ) -> float:
        """Compute final sentiment score (0-100)."""
        score = 50.0

        # Hype index contribution (max +/- 20)
        if analysis.hype_index > 70:
            score += 15
        elif analysis.hype_index > 50:
            score += 8
        elif analysis.hype_index < 30:
            score -= 10

        # Organic ratio (max +/- 15)
        if analysis.organic_ratio > 0.7:
            score += 15
        elif analysis.organic_ratio > 0.5:
            score += 5
        elif analysis.organic_ratio < 0.3:
            score -= 15

        # Sentiment direction (max +/- 10)
        if analysis.overall_sentiment > 0.5:
            score += 10
        elif analysis.overall_sentiment > 0:
            score += 5
        elif analysis.overall_sentiment < -0.5:
            score -= 10
        elif analysis.overall_sentiment < 0:
            score -= 5

        # Price-sentiment divergence (contrarian signal)
        if price_change_7d < -15 and analysis.overall_sentiment > 0.3:
            score += 5  # Resilient sentiment = potential opportunity
        elif price_change_7d > 30 and analysis.overall_sentiment < 0:
            score -= 5  # Price up but sentiment down = distribution

        return max(0, min(100, score))
