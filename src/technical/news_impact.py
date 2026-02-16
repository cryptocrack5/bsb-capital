"""
BSB Capital - News & Event Impact Module
Quantifies news sentiment and event-driven price catalysts.

Methodologies:
- Event Study methodology for token unlocks
- NLP-based news sentiment aggregation
- Buy the Rumor, Sell the News quantification
- Regulatory news impact weighting
"""

import logging
from typing import Optional

from src.models.schemas import NewsImpactAnalysis

logger = logging.getLogger(__name__)


# Event type impact weights (based on historical crypto event studies)
EVENT_IMPACT_WEIGHTS = {
    "token_unlock": -0.6,  # Historically negative (sell pressure)
    "mainnet_launch": 0.7,  # Positive but often "sell the news"
    "partnership": 0.4,  # Moderate positive
    "exchange_listing": 0.5,  # Positive short-term
    "hack_exploit": -0.9,  # Severely negative
    "regulatory_positive": 0.6,  # Significant positive
    "regulatory_negative": -0.8,  # Significant negative
    "airdrop": 0.3,  # Mixed - creates short-term demand then sell
    "upgrade": 0.5,  # Generally positive
    "team_departure": -0.5,  # Negative signal
    "treasury_diversification": -0.3,  # Sell pressure concern
    "burn_event": 0.4,  # Deflationary = positive
}

# Keywords for news classification
NEWS_KEYWORDS = {
    "positive": [
        "partnership", "integration", "launch", "upgrade", "adoption",
        "institutional", "approval", "etf", "expansion", "milestone",
        "revenue", "profit", "growth", "bullish", "breakthrough",
    ],
    "negative": [
        "hack", "exploit", "vulnerability", "sec", "lawsuit", "ban",
        "crash", "dump", "rug", "scam", "delay", "regulatory",
        "investigation", "sanction", "bearish", "default",
    ],
    "unlock": [
        "unlock", "vesting", "cliff", "release", "distribute",
    ],
    "regulatory": [
        "sec", "regulation", "compliance", "legal", "cftc",
        "ban", "restrict", "license", "framework", "legislation",
    ],
}


class NewsImpactAnalyzer:
    """
    Analyzes news and events for their potential price impact.

    The news impact score filters noise using:
    1. Event classification by type
    2. Historical impact weighting
    3. Recency decay factor
    4. Volume of coverage (consensus signal)
    """

    def __init__(self):
        self._vader = None

    def _get_vader(self):
        """Lazy-load VADER."""
        if self._vader is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                self._vader = SentimentIntensityAnalyzer()
            except ImportError:
                self._vader = None
        return self._vader

    def analyze(
        self,
        token_name: str,
        description: str = "",
        recent_news: Optional[list[str]] = None,
        has_upcoming_unlocks: bool = False,
        inflation_rate: float = 0.0,
    ) -> NewsImpactAnalysis:
        """Run news impact analysis."""
        result = NewsImpactAnalysis()

        # Analyze description and available text
        all_texts = [description] if description else []
        if recent_news:
            all_texts.extend(recent_news)

        if all_texts:
            result.recent_news_sentiment = self._analyze_sentiment(all_texts)
            result.significant_events = self._extract_events(all_texts)
            result.regulatory_risk = self._assess_regulatory_risk(all_texts)

        # Token unlock risk
        if has_upcoming_unlocks or inflation_rate > 50:
            result.upcoming_unlocks.append(
                f"Alta inflacion pendiente ({inflation_rate:.0f}%): riesgo de presion vendedora"
            )

        # BTRSTN risk (Buy the Rumor, Sell the News)
        result.buy_rumor_sell_news_risk = self._assess_btrstn_risk(
            result, description
        )

        # News volume anomaly
        if recent_news and len(recent_news) > 10:
            result.news_volume_anomaly = True

        # Score
        result.score = self._compute_score(result)

        return result

    def _analyze_sentiment(self, texts: list[str]) -> float:
        """Analyze sentiment across multiple texts."""
        vader = self._get_vader()
        if not vader:
            return self._keyword_sentiment(texts)

        scores = []
        for text in texts:
            if text:
                score = vader.polarity_scores(text)["compound"]
                scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0

    def _keyword_sentiment(self, texts: list[str]) -> float:
        """Fallback keyword-based sentiment when VADER unavailable."""
        positive_count = 0
        negative_count = 0

        for text in texts:
            text_lower = text.lower()
            for kw in NEWS_KEYWORDS["positive"]:
                if kw in text_lower:
                    positive_count += 1
            for kw in NEWS_KEYWORDS["negative"]:
                if kw in text_lower:
                    negative_count += 1

        total = positive_count + negative_count
        if total == 0:
            return 0.0
        return (positive_count - negative_count) / total

    def _extract_events(self, texts: list[str]) -> list[str]:
        """Extract significant events from text."""
        events = []
        combined = " ".join(texts).lower()

        for event_type, weight in EVENT_IMPACT_WEIGHTS.items():
            keywords = event_type.replace("_", " ")
            if keywords in combined:
                direction = "positivo" if weight > 0 else "negativo"
                events.append(
                    f"{event_type}: Impacto estimado {direction} "
                    f"(peso: {weight:+.1f})"
                )

        return events[:10]  # Cap at 10 events

    def _assess_regulatory_risk(self, texts: list[str]) -> float:
        """
        Assess regulatory risk (0-100).

        Based on frequency and severity of regulatory keywords.
        """
        combined = " ".join(texts).lower()
        risk_score = 0.0

        for kw in NEWS_KEYWORDS["regulatory"]:
            count = combined.count(kw)
            if count > 0:
                risk_score += min(15, count * 5)

        return min(100, risk_score)

    def _assess_btrstn_risk(
        self, analysis: NewsImpactAnalysis, description: str
    ) -> float:
        """
        Assess "Buy the Rumor, Sell the News" risk.

        High risk when:
        - Major upcoming events with high anticipation
        - Recent price run-up coinciding with event approach
        - High news volume (market already priced in)
        """
        risk = 20.0  # Base risk

        # High positive sentiment + upcoming events = BTRSTN risk
        if analysis.recent_news_sentiment > 0.5 and analysis.significant_events:
            risk += 20

        # News volume anomaly
        if analysis.news_volume_anomaly:
            risk += 15

        # Upcoming unlocks add to sell pressure
        if analysis.upcoming_unlocks:
            risk += 15

        # Very positive description might indicate overhype
        if analysis.recent_news_sentiment > 0.7:
            risk += 10

        return min(100, risk)

    def _compute_score(self, analysis: NewsImpactAnalysis) -> float:
        """Compute news impact score (0-100). 50 = neutral."""
        score = 50.0

        # Sentiment impact (+/- 20)
        score += analysis.recent_news_sentiment * 20

        # Regulatory risk (max -20)
        score -= analysis.regulatory_risk * 0.2

        # BTRSTN risk (max -10)
        if analysis.buy_rumor_sell_news_risk > 60:
            score -= 10
        elif analysis.buy_rumor_sell_news_risk > 40:
            score -= 5

        # Upcoming unlocks (max -10)
        score -= len(analysis.upcoming_unlocks) * 5

        return max(0, min(100, score))
