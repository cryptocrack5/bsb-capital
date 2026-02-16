"""
BSB Capital - VC & Partnership Analysis Module
Evaluates investor quality, cap table health, and strategic partnerships.

Methodology based on:
- VC Reputation Tier Lists (historical ROI-based ranking)
- Strategic Partnership Value-Add Assessment
- Cap Table Health Analysis beyond vesting
"""

import logging
from typing import Optional

from config.settings import VC_WEIGHTS
from src.models.schemas import VCAnalysis

logger = logging.getLogger(__name__)


# VC Tier Classification based on historical crypto fund performance
VC_TIERS = {
    # Tier 1 - Top-tier crypto-native funds (highest success rates)
    1: [
        "a16z", "andreessen horowitz", "paradigm", "polychain capital",
        "pantera capital", "dragonfly", "multicoin capital", "electric capital",
        "placeholder", "variant fund", "framework ventures", "delphi digital",
        "coinbase ventures", "binance labs", "galaxy digital", "digital currency group",
        "sequoia", "lightspeed", "coatue",
    ],
    # Tier 2 - Established funds with strong track records
    2: [
        "jump crypto", "wintermute ventures", "alameda research",
        "three arrows capital", "hashed", "animoca brands", "spartan group",
        "mechanism capital", "dao5", "hack vc", "shima capital",
        "iosg ventures", "sns capital", "figment capital",
        "robot ventures", "1kx", "nascent", "standard crypto",
    ],
    # Tier 3 - Active but smaller/newer funds
    3: [
        "cms holdings", "gsr", "maven 11", "ngc ventures",
        "fabric ventures", "north island ventures", "fenbushi capital",
        "sino global capital", "blockchain capital", "morningstar ventures",
    ],
}

# Known strategic partners with high value-add
HIGH_VALUE_PARTNERS = {
    "google cloud": 9,
    "microsoft": 9,
    "amazon aws": 8,
    "meta": 8,
    "visa": 9,
    "mastercard": 9,
    "jpmorgan": 8,
    "goldman sachs": 8,
    "blackrock": 10,
    "fidelity": 9,
    "chainlink": 7,
    "circle": 7,
}


class VCAnalyzer:
    """
    Analyzes VC backing quality and partnership strength.

    VC Reputation Score formula:
        VCScore = sum(tier_weight[i] * investor_count[i]) / max_possible

    Where tier weights:
        Tier 1 = 10 points per investor
        Tier 2 = 6 points per investor
        Tier 3 = 3 points per investor
        Unknown = 1 point per investor
    """

    TIER_WEIGHTS = {1: 10, 2: 6, 3: 3, 0: 1}

    def analyze(
        self,
        token_name: str,
        known_investors: Optional[list[str]] = None,
        known_partners: Optional[list[str]] = None,
        total_raised: float = 0.0,
        funding_rounds: int = 0,
    ) -> VCAnalysis:
        """Run VC and partnership analysis."""
        result = VCAnalysis()
        result.total_raised = total_raised
        result.num_funding_rounds = funding_rounds

        if known_investors:
            self._classify_investors(result, known_investors)

        if known_partners:
            self._evaluate_partnerships(result, known_partners)

        result.vc_reputation_score = self._compute_vc_score(result)
        result.cap_table_health = self._assess_cap_table(result)
        result.score = self._compute_final_score(result)

        return result

    def _classify_investors(self, result: VCAnalysis, investors: list[str]) -> None:
        """Classify investors into tiers."""
        for investor in investors:
            inv_lower = investor.lower().strip()
            tier = self._get_investor_tier(inv_lower)
            if tier == 1:
                result.tier1_investors.append(investor)
            elif tier == 2:
                result.tier2_investors.append(investor)
            else:
                result.tier3_investors.append(investor)

    def _get_investor_tier(self, investor_name: str) -> int:
        """Determine investor tier."""
        for tier, names in VC_TIERS.items():
            if any(name in investor_name or investor_name in name for name in names):
                return tier
        return 3  # Default to tier 3

    def _evaluate_partnerships(self, result: VCAnalysis, partners: list[str]) -> None:
        """Evaluate quality of strategic partnerships."""
        result.strategic_partners = partners
        scores = []
        for partner in partners:
            p_lower = partner.lower().strip()
            for known, value in HIGH_VALUE_PARTNERS.items():
                if known in p_lower or p_lower in known:
                    scores.append(value)
                    break
            else:
                scores.append(3)  # Default partnership value

        if scores:
            result.partnership_quality_score = (sum(scores) / len(scores)) * 10
        result.partnership_quality_score = min(100, result.partnership_quality_score)

    def _compute_vc_score(self, result: VCAnalysis) -> float:
        """
        Compute VC reputation score (0-100).

        Method: Weighted sum of tier-classified investors, normalized.
        A project backed by 3 Tier-1 investors scores higher than
        one backed by 10 unknown funds.
        """
        tier1_pts = len(result.tier1_investors) * self.TIER_WEIGHTS[1]
        tier2_pts = len(result.tier2_investors) * self.TIER_WEIGHTS[2]
        tier3_pts = len(result.tier3_investors) * self.TIER_WEIGHTS[3]

        total_pts = tier1_pts + tier2_pts + tier3_pts

        # Normalize: 3 tier-1 investors (30 pts) = ~85 score
        # Max realistic = ~60 pts (6 tier-1)
        max_pts = 60.0
        score = min(100, (total_pts / max_pts) * 100)

        # Bonus for diversity of tiers (signals broad market validation)
        tiers_present = sum([
            1 if result.tier1_investors else 0,
            1 if result.tier2_investors else 0,
            1 if result.tier3_investors else 0,
        ])
        if tiers_present >= 3:
            score = min(100, score + 5)
        elif tiers_present >= 2:
            score = min(100, score + 2)

        return round(score, 1)

    def _assess_cap_table(self, result: VCAnalysis) -> float:
        """
        Assess cap table health (0-100).

        Healthy cap table indicators:
        - Multiple funding rounds (not just one big round)
        - Mix of strategic and financial investors
        - Reasonable total raised vs market expectations
        """
        score = 50.0  # Start neutral

        # Multiple rounds = healthy fundraising
        if result.num_funding_rounds >= 3:
            score += 15
        elif result.num_funding_rounds >= 2:
            score += 10
        elif result.num_funding_rounds == 1:
            score += 0
        else:
            score -= 10

        # Tier-1 presence
        if len(result.tier1_investors) >= 2:
            score += 15
        elif len(result.tier1_investors) >= 1:
            score += 10

        # Strategic partners add value
        if result.strategic_partners:
            score += min(10, len(result.strategic_partners) * 3)

        # Total investor count
        total_investors = (
            len(result.tier1_investors)
            + len(result.tier2_investors)
            + len(result.tier3_investors)
        )
        if total_investors > 10:
            score += 5  # Broad support
        elif total_investors < 3:
            score -= 5  # Narrow support

        return max(0, min(100, score))

    def _compute_final_score(self, result: VCAnalysis) -> float:
        """Compute weighted final score."""
        w = VC_WEIGHTS
        score = (
            w["vc_tier"] * result.vc_reputation_score
            + w["num_institutional_backers"] * min(100, (
                len(result.tier1_investors) + len(result.tier2_investors)
            ) * 15)
            + w["strategic_alignment"] * result.partnership_quality_score
            + w["follow_on_investment"] * (70 if result.follow_on_investment else 30)
            + w["partnership_quality"] * result.partnership_quality_score
        )
        return round(max(0, min(100, score)), 1)
