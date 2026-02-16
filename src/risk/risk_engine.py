"""
BSB Capital - Risk Assessment Engine
Comprehensive risk evaluation combining all analysis dimensions.

Evaluates:
- Tokenomics structural risks (dumping structure detection)
- Moral hazard analysis (contract theory framework)
- Incentive alignment assessment
- Traffic light risk system (Red/Yellow/Green)
"""

import logging

from config.settings import (
    FINAL_SCORE_WEIGHTS,
    RATING_STRONG_BUY,
    RATING_BUY,
    RATING_NEUTRAL,
    RATING_SELL,
)
from src.models.schemas import (
    RiskSignal,
    RiskFlag,
    RiskAssessment,
    TokenomicsAnalysis,
    QualitativeAnalysis,
    TechnicalAnalysis,
    Verdict,
)

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Comprehensive risk assessment engine.

    Combines tokenomics, qualitative, and technical signals into
    a unified risk profile with traffic-light classification.
    """

    def assess(
        self,
        tokenomics: TokenomicsAnalysis,
        qualitative: QualitativeAnalysis,
        technical: TechnicalAnalysis,
    ) -> RiskAssessment:
        """Run full risk assessment."""
        result = RiskAssessment()

        # Collect all risk flags from tokenomics
        for flag in tokenomics.risk_signals:
            if flag.signal == RiskSignal.RED:
                result.red_flags.append(flag)
            elif flag.signal == RiskSignal.YELLOW:
                result.yellow_flags.append(flag)
            else:
                result.green_flags.append(flag)

        # Add qualitative risk flags
        self._add_qualitative_risks(result, qualitative)

        # Add technical risk flags
        self._add_technical_risks(result, technical)

        # Structural assessments
        result.low_float_high_fdv = tokenomics.fdv_mcap_ratio > 10
        result.mercenary_incentives = self._detect_mercenary_incentives(
            tokenomics, qualitative
        )
        result.moral_hazard_risk = self._assess_moral_hazard(tokenomics, qualitative)
        result.dumping_structure = self._is_dumping_structure(
            tokenomics, qualitative, result
        )

        # Overall risk score
        result.overall_risk_score = self._compute_overall_score(
            tokenomics, qualitative, technical, result
        )

        return result

    def compute_verdict(
        self,
        tokenomics: TokenomicsAnalysis,
        qualitative: QualitativeAnalysis,
        technical: TechnicalAnalysis,
        risk: RiskAssessment,
    ) -> tuple[float, Verdict]:
        """
        Compute final weighted score and verdict.

        Final Score = w1*Tokenomics + w2*Qualitative + w3*Technical + w4*Risk
        """
        w = FINAL_SCORE_WEIGHTS

        final_score = (
            w["tokenomics"] * tokenomics.score
            + w["qualitative"] * qualitative.score
            + w["technical"] * technical.score
            + w["risk"] * risk.overall_risk_score
        )

        # Apply confidence adjustment from volatility
        confidence = technical.volatility.confidence_adjustment
        if confidence < 0.5:
            # In extreme volatility, pull score toward neutral
            final_score = final_score * 0.7 + 50 * 0.3

        final_score = max(0, min(100, final_score))

        # Determine verdict
        if final_score >= RATING_STRONG_BUY:
            verdict = Verdict.STRONG_BUY
        elif final_score >= RATING_BUY:
            verdict = Verdict.BUY
        elif final_score >= RATING_NEUTRAL:
            verdict = Verdict.NEUTRAL
        elif final_score >= RATING_SELL:
            verdict = Verdict.SELL
        else:
            verdict = Verdict.STRONG_SELL

        # Override: dumping structure always caps at NEUTRAL
        if risk.dumping_structure and verdict in (Verdict.STRONG_BUY, Verdict.BUY):
            verdict = Verdict.NEUTRAL
            final_score = min(final_score, RATING_NEUTRAL + 5)

        return round(final_score, 1), verdict

    def _add_qualitative_risks(
        self, result: RiskAssessment, qual: QualitativeAnalysis
    ) -> None:
        """Add risk flags from qualitative analysis."""
        # Sentiment risks
        if qual.sentiment.organic_ratio < 0.3:
            result.red_flags.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Sentimiento",
                description="Bajo ratio organico: posible manipulacion de redes sociales",
                severity=6.0,
            ))
        elif qual.sentiment.organic_ratio > 0.7:
            result.green_flags.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Sentimiento",
                description="Alto ratio organico: comunidad genuina",
                severity=1.0,
            ))

        if qual.sentiment.hype_index > 80:
            result.yellow_flags.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="Hype",
                description=f"Indice de Hype muy alto ({qual.sentiment.hype_index:.0f}/100): posible burbuja",
                severity=5.0,
            ))

        # Team risks
        if qual.team.team_score < 30:
            result.red_flags.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Equipo",
                description="Puntuacion de equipo baja: informacion insuficiente o equipo debil",
                severity=7.0,
            ))
        elif qual.team.team_score > 70:
            result.green_flags.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Equipo",
                description=f"Equipo solido (score: {qual.team.team_score:.0f}/100)",
                severity=1.0,
            ))

        if qual.team.development_activity_score < 20:
            result.red_flags.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Desarrollo",
                description="Actividad de desarrollo muy baja o inexistente",
                severity=8.0,
            ))
        elif qual.team.development_activity_score > 60:
            result.green_flags.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Desarrollo",
                description="Alta actividad de desarrollo en GitHub",
                severity=1.0,
            ))

        # VC risks
        if qual.vc.score < 20:
            result.yellow_flags.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="Inversores",
                description="Sin respaldo de inversores institucionales reconocidos",
                severity=4.0,
            ))
        elif qual.vc.tier1_investors:
            result.green_flags.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Inversores",
                description=f"Respaldado por fondos Tier-1: {', '.join(qual.vc.tier1_investors[:3])}",
                severity=1.0,
            ))

    def _add_technical_risks(
        self, result: RiskAssessment, tech: TechnicalAnalysis
    ) -> None:
        """Add risk flags from technical analysis."""
        # Volatility regime
        from src.models.schemas import VolatilityRegime
        if tech.volatility.market_regime == VolatilityRegime.EXTREME:
            result.red_flags.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Volatilidad",
                description="Regimen de volatilidad EXTREMA: alto riesgo operativo",
                severity=8.0,
            ))
        elif tech.volatility.market_regime == VolatilityRegime.HIGH:
            result.yellow_flags.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="Volatilidad",
                description="Volatilidad alta: ajustar tamano de posicion",
                severity=5.0,
            ))
        elif tech.volatility.market_regime == VolatilityRegime.LOW:
            result.green_flags.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Volatilidad",
                description="Baja volatilidad: entorno estable",
                severity=1.0,
            ))

        # Drawdown
        if tech.volatility.max_drawdown_30d < -30:
            result.red_flags.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Drawdown",
                description=f"Drawdown severo 30d: {tech.volatility.max_drawdown_30d:.1f}%",
                severity=7.0,
            ))

        # Death cross
        if tech.momentum.death_cross:
            result.red_flags.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Tecnico",
                description="Death Cross detectado (MA50 cruza debajo de MA200)",
                severity=6.0,
            ))
        elif tech.momentum.golden_cross:
            result.green_flags.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Tecnico",
                description="Golden Cross detectado (MA50 cruza encima de MA200)",
                severity=1.0,
            ))

    def _detect_mercenary_incentives(
        self, tokenomics: TokenomicsAnalysis, qual: QualitativeAnalysis
    ) -> bool:
        """
        Detect if token structure attracts "mercenary capital" (farmers).

        Mercenary signals:
        - High staking APY that is purely inflationary
        - Very high insider allocation with short vesting
        - No real utility demand
        """
        from src.models.schemas import UtilityType

        staking_inflationary = (
            UtilityType.STAKING_INFLATIONARY in tokenomics.utility.utility_types
            and tokenomics.utility.staking_is_inflationary
        )
        short_vesting = tokenomics.vesting.vesting_duration_months < 12
        no_real_demand = not tokenomics.utility.has_real_demand

        mercenary_count = sum([staking_inflationary, short_vesting, no_real_demand])
        return mercenary_count >= 2

    def _assess_moral_hazard(
        self, tokenomics: TokenomicsAnalysis, qual: QualitativeAnalysis
    ) -> float:
        """
        Assess moral hazard risk (0-100).

        Based on contract theory: does the token structure incentivize
        the team to deliver (production) or to extract value (dumping)?

        Optimal model: "Pre-sale of Production + Revenue Sharing"
        Bad model: "High TGE unlock + No revenue link + Inflationary staking"
        """
        risk = 20.0  # Base

        # High TGE unlock = team can dump immediately
        if tokenomics.vesting.tge_unlock_percentage > 30:
            risk += 20
        elif tokenomics.vesting.tge_unlock_percentage > 15:
            risk += 10

        # No revenue sharing = no skin in the game
        if not tokenomics.utility.revenue_share:
            risk += 15

        # Inflationary staking only = dilutive without value creation
        from src.models.schemas import UtilityType
        if (
            UtilityType.STAKING_INFLATIONARY in tokenomics.utility.utility_types
            and not tokenomics.utility.has_real_demand
        ):
            risk += 15

        # Low development activity = possible abandonment
        if qual.team.development_activity_score < 20:
            risk += 15

        # High insider allocation + short vesting = extraction
        if (
            tokenomics.distribution.insider_percentage > 40
            and tokenomics.vesting.vesting_duration_months < 24
        ):
            risk += 15

        return min(100, risk)

    def _is_dumping_structure(
        self,
        tokenomics: TokenomicsAnalysis,
        qual: QualitativeAnalysis,
        risk: RiskAssessment,
    ) -> bool:
        """
        Determine if the token structure is designed for "dumping".

        A dumping structure has 3+ of these characteristics:
        1. Low float / High FDV
        2. Short vesting (< 2 years)
        3. High insider allocation (>40%)
        4. No real utility
        5. No revenue sharing
        6. Mercenary incentives present
        """
        dumping_signals = 0

        if risk.low_float_high_fdv:
            dumping_signals += 1
        if tokenomics.vesting.vesting_duration_months < 24:
            dumping_signals += 1
        if tokenomics.distribution.insider_percentage > 40:
            dumping_signals += 1
        if not tokenomics.utility.has_real_demand:
            dumping_signals += 1
        if not tokenomics.utility.revenue_share:
            dumping_signals += 1
        if risk.mercenary_incentives:
            dumping_signals += 1

        return dumping_signals >= 3

    def _compute_overall_score(
        self,
        tokenomics: TokenomicsAnalysis,
        qual: QualitativeAnalysis,
        tech: TechnicalAnalysis,
        risk: RiskAssessment,
    ) -> float:
        """Compute overall risk score (0-100). Higher = safer."""
        score = 50.0

        # Red flags penalty (max -40)
        red_severity = sum(f.severity for f in risk.red_flags)
        score -= min(40, red_severity * 2)

        # Yellow flags penalty (max -15)
        yellow_severity = sum(f.severity for f in risk.yellow_flags)
        score -= min(15, yellow_severity * 1)

        # Green flags bonus (max +30)
        green_count = len(risk.green_flags)
        score += min(30, green_count * 5)

        # Structural penalties
        if risk.dumping_structure:
            score -= 20
        if risk.mercenary_incentives:
            score -= 10
        if risk.moral_hazard_risk > 60:
            score -= 10

        return max(0, min(100, score))
