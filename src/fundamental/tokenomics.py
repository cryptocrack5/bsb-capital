"""
BSB Capital - Tokenomics Analysis Module
Evaluates distribution, emission, vesting, inflation, and utility.
"""

import logging
from typing import Optional

from config.settings import (
    INSIDER_ALLOCATION_HIGH_RISK,
    INSIDER_ALLOCATION_MODERATE_RISK,
    INFLATION_HIGH_RISK,
    INFLATION_MODERATE_RISK,
    INFLATION_LOW_RISK,
    VESTING_STRONG,
    VESTING_MODERATE,
    FDV_MCAP_HIGH_RISK,
    FDV_MCAP_MODERATE_RISK,
    PU_OVERVALUED,
    PU_FAIR,
)
from src.models.schemas import (
    TokenMarketData,
    TokenType,
    UtilityType,
    RiskSignal,
    RiskFlag,
    DistributionData,
    VestingSchedule,
    InflationMetrics,
    TokenUtility,
    TokenomicsAnalysis,
)

logger = logging.getLogger(__name__)


class TokenomicsAnalyzer:
    """Performs fundamental tokenomics analysis."""

    def analyze(
        self,
        token: TokenMarketData,
        community_data: dict,
        distribution_override: Optional[DistributionData] = None,
        vesting_override: Optional[VestingSchedule] = None,
    ) -> TokenomicsAnalysis:
        """Run complete tokenomics analysis."""
        result = TokenomicsAnalysis()

        # Distribution
        if distribution_override:
            result.distribution = distribution_override
        else:
            result.distribution = self._estimate_distribution(token, community_data)

        # Vesting
        if vesting_override:
            result.vesting = vesting_override
        else:
            result.vesting = self._estimate_vesting(token)

        # Inflation
        result.inflation = self._calculate_inflation(token)

        # Utility
        result.utility = self._analyze_utility(token, community_data)

        # FDV/MCap ratio
        if token.market_cap > 0:
            result.fdv_mcap_ratio = token.fully_diluted_valuation / token.market_cap
        else:
            result.fdv_mcap_ratio = 0

        # PU Ratio (for L1s)
        result.pu_ratio = self._calculate_pu_ratio(token, community_data)

        # Risk signals
        result.risk_signals = self._evaluate_risk_signals(result, token)

        # Composite score
        result.score = self._compute_score(result)

        return result

    def _estimate_distribution(
        self, token: TokenMarketData, community_data: dict
    ) -> DistributionData:
        """Estimate token distribution from available data."""
        dist = DistributionData()
        desc = community_data.get("description", "").lower()
        categories = community_data.get("categories", [])

        # Heuristic estimation based on token type and available data
        if token.token_type == TokenType.MEME:
            dist.community_allocation = 90.0
            dist.team_allocation = 5.0
            dist.investor_allocation = 0.0
            dist.ecosystem_allocation = 5.0
        elif token.token_type == TokenType.L1:
            dist.team_allocation = 15.0
            dist.investor_allocation = 15.0
            dist.community_allocation = 30.0
            dist.ecosystem_allocation = 25.0
            dist.foundation_allocation = 10.0
            dist.treasury_allocation = 5.0
        elif token.token_type == TokenType.DEFI:
            dist.team_allocation = 20.0
            dist.investor_allocation = 20.0
            dist.community_allocation = 25.0
            dist.ecosystem_allocation = 20.0
            dist.treasury_allocation = 15.0
        else:
            dist.team_allocation = 18.0
            dist.investor_allocation = 18.0
            dist.community_allocation = 30.0
            dist.ecosystem_allocation = 20.0
            dist.treasury_allocation = 14.0

        # Check description for clues
        if "fair launch" in desc:
            dist.community_allocation = max(dist.community_allocation, 60.0)
            dist.team_allocation = min(dist.team_allocation, 10.0)
            dist.investor_allocation = 0.0

        dist.insider_percentage = dist.team_allocation + dist.investor_allocation
        dist.community_percentage = (
            dist.community_allocation
            + dist.ecosystem_allocation
            + dist.airdrop_allocation
        )

        # Supply concentration estimate
        if token.circulating_supply > 0 and token.total_supply > 0:
            supply_ratio = token.circulating_supply / token.total_supply
            if supply_ratio < 0.3:
                dist.top_10_wallet_concentration = 70.0 + (1 - supply_ratio) * 20
            elif supply_ratio < 0.6:
                dist.top_10_wallet_concentration = 40.0 + (1 - supply_ratio) * 30
            else:
                dist.top_10_wallet_concentration = 20.0 + (1 - supply_ratio) * 20

        dist.data_available = False  # Mark as estimated
        return dist

    def _estimate_vesting(self, token: TokenMarketData) -> VestingSchedule:
        """Estimate vesting schedule from supply data."""
        vesting = VestingSchedule()

        if token.total_supply > 0 and token.circulating_supply > 0:
            locked_ratio = 1 - (token.circulating_supply / token.total_supply)
            vesting.tokens_locked = token.total_supply - token.circulating_supply
            vesting.tokens_unlocked = token.circulating_supply

            # Heuristic: estimate based on locked ratio
            if locked_ratio > 0.7:
                vesting.vesting_duration_months = 48
                vesting.cliff_months = 12
                vesting.tge_unlock_percentage = (1 - locked_ratio) * 100
            elif locked_ratio > 0.4:
                vesting.vesting_duration_months = 36
                vesting.cliff_months = 6
                vesting.tge_unlock_percentage = (1 - locked_ratio) * 100
            elif locked_ratio > 0.1:
                vesting.vesting_duration_months = 24
                vesting.cliff_months = 3
                vesting.tge_unlock_percentage = (1 - locked_ratio) * 100
            else:
                vesting.vesting_duration_months = 0
                vesting.cliff_months = 0
                vesting.tge_unlock_percentage = 100.0

            if locked_ratio > 0 and vesting.vesting_duration_months > 0:
                vesting.monthly_unlock_rate = (
                    locked_ratio * 100 / vesting.vesting_duration_months
                )

        vesting.data_available = False
        return vesting

    def _calculate_inflation(self, token: TokenMarketData) -> InflationMetrics:
        """Calculate inflation metrics."""
        metrics = InflationMetrics()

        circ = token.circulating_supply
        total = token.total_supply
        max_sup = token.max_supply

        if circ > 0 and total > 0:
            tokens_to_unlock = total - circ
            metrics.max_inflation = (tokens_to_unlock / circ) * 100
            metrics.supply_ratio = circ / total

            # Estimate annualized inflation
            if max_sup and max_sup > 0:
                remaining = max_sup - circ
                if remaining > 0:
                    # Assume linear emission over estimated remaining years
                    estimated_years = max(1, remaining / (total * 0.1))
                    metrics.current_inflation_rate = (remaining / circ / estimated_years) * 100
                    metrics.years_to_full_dilution = remaining / (total * 0.1)
                    metrics.emission_schedule_type = "estimated_linear"
            else:
                if tokens_to_unlock > 0:
                    metrics.current_inflation_rate = metrics.max_inflation / 4
                    metrics.emission_schedule_type = "no_max_supply"

        return metrics

    def _analyze_utility(
        self, token: TokenMarketData, community_data: dict
    ) -> TokenUtility:
        """Analyze token utility."""
        utility = TokenUtility()
        desc = community_data.get("description", "").lower()
        categories = [c.lower() for c in community_data.get("categories", []) if c]

        # Detect utility types
        if token.token_type == TokenType.L1 or token.token_type == TokenType.L2:
            utility.utility_types.append(UtilityType.GAS)
            utility.gas_token = True
            utility.has_real_demand = True

        if any(kw in desc for kw in ["governance", "vote", "dao"]):
            utility.utility_types.append(UtilityType.GOVERNANCE)
            utility.governance_active = True

        if any(kw in desc for kw in ["staking", "stake", "validator"]):
            if any(kw in desc for kw in ["real yield", "revenue", "fee share", "dividend"]):
                utility.utility_types.append(UtilityType.STAKING_REAL)
                utility.staking_is_inflationary = False
                utility.revenue_share = True
                utility.has_real_demand = True
            else:
                utility.utility_types.append(UtilityType.STAKING_INFLATIONARY)
                utility.staking_is_inflationary = True

        if any(kw in desc for kw in ["payment", "pay", "transfer", "remittance"]):
            utility.utility_types.append(UtilityType.PAYMENTS)

        if any(kw in desc for kw in ["collateral", "borrow", "lending", "cdp"]):
            utility.utility_types.append(UtilityType.COLLATERAL)
            utility.has_real_demand = True

        if any(kw in desc for kw in ["access", "subscription", "membership"]):
            utility.utility_types.append(UtilityType.ACCESS)

        if not utility.utility_types:
            utility.utility_types.append(UtilityType.NONE)

        # Build description
        utility.description = ", ".join(u.value for u in utility.utility_types)

        return utility

    def _calculate_pu_ratio(
        self, token: TokenMarketData, community_data: dict
    ) -> Optional[float]:
        """
        Calculate Price/Utility ratio for L1/L2 tokens.
        PU = Market Cap / (Annualized Transaction Fees * Velocity Factor)
        Estimated when direct data isn't available.
        """
        if token.token_type not in (TokenType.L1, TokenType.L2):
            return None

        if token.market_cap == 0 or token.volume_24h == 0:
            return None

        # Estimate annualized "utility value" from volume as proxy
        annualized_volume = token.volume_24h * 365
        # Assume ~0.1% average fee rate and velocity factor
        estimated_annual_fees = annualized_volume * 0.001
        velocity_factor = min(annualized_volume / token.market_cap, 50)

        if estimated_annual_fees > 0:
            pu_ratio = token.market_cap / estimated_annual_fees
            return round(pu_ratio, 2)
        return None

    def _evaluate_risk_signals(
        self, analysis: TokenomicsAnalysis, token: TokenMarketData
    ) -> list[RiskFlag]:
        """Generate risk signals based on tokenomics analysis."""
        signals = []

        # Distribution risks
        insider_pct = analysis.distribution.insider_percentage
        if insider_pct > INSIDER_ALLOCATION_HIGH_RISK:
            signals.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Distribucion",
                description=f"Alta concentracion de insiders: {insider_pct:.1f}% asignado a equipo/inversores",
                severity=8.0,
            ))
        elif insider_pct > INSIDER_ALLOCATION_MODERATE_RISK:
            signals.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="Distribucion",
                description=f"Concentracion moderada de insiders: {insider_pct:.1f}%",
                severity=5.0,
            ))
        else:
            signals.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Distribucion",
                description=f"Distribucion favorable a comunidad: {insider_pct:.1f}% insiders",
                severity=2.0,
            ))

        # Inflation risks
        max_inf = analysis.inflation.max_inflation
        if max_inf > INFLATION_HIGH_RISK:
            signals.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Inflacion",
                description=f"Inflacion maxima muy alta: {max_inf:.1f}% tokens por desbloquear vs circulante",
                severity=9.0,
            ))
        elif max_inf > INFLATION_MODERATE_RISK:
            signals.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="Inflacion",
                description=f"Inflacion maxima moderada: {max_inf:.1f}%",
                severity=5.0,
            ))
        elif max_inf > 0:
            signals.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Inflacion",
                description=f"Inflacion maxima controlada: {max_inf:.1f}%",
                severity=2.0,
            ))

        # FDV risk
        fdv_ratio = analysis.fdv_mcap_ratio
        if fdv_ratio > FDV_MCAP_HIGH_RISK:
            signals.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Low Float / High FDV",
                description=f"FDV es {fdv_ratio:.1f}x el Market Cap - alto riesgo de dilucion",
                severity=9.0,
            ))
        elif fdv_ratio > FDV_MCAP_MODERATE_RISK:
            signals.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="FDV",
                description=f"FDV es {fdv_ratio:.1f}x el Market Cap",
                severity=5.0,
            ))

        # Vesting risks
        vesting_months = analysis.vesting.vesting_duration_months
        if vesting_months >= VESTING_STRONG:
            signals.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Vesting",
                description=f"Vesting largo estimado: {vesting_months} meses",
                severity=2.0,
            ))
        elif vesting_months >= VESTING_MODERATE:
            signals.append(RiskFlag(
                signal=RiskSignal.YELLOW,
                category="Vesting",
                description=f"Vesting moderado: {vesting_months} meses",
                severity=5.0,
            ))
        elif vesting_months > 0:
            signals.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Vesting",
                description=f"Vesting corto: {vesting_months} meses - riesgo de dump",
                severity=7.0,
            ))

        # Burn/Buyback mechanisms
        if analysis.vesting.has_burn_mechanism:
            signals.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Mecanismo de Quema",
                description="Tiene mecanismo de quema de tokens",
                severity=1.0,
            ))
        if analysis.vesting.has_buyback_mechanism:
            signals.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Buyback",
                description="Tiene programa de recompra de tokens",
                severity=1.0,
            ))

        # Utility assessment
        if not analysis.utility.has_real_demand:
            signals.append(RiskFlag(
                signal=RiskSignal.RED,
                category="Utilidad",
                description="No se detecta demanda intrinseca real para el token",
                severity=7.0,
            ))
        else:
            signals.append(RiskFlag(
                signal=RiskSignal.GREEN,
                category="Utilidad",
                description=f"Demanda intrinseca detectada: {analysis.utility.description}",
                severity=1.0,
            ))

        # PU Ratio interpretation
        if analysis.pu_ratio is not None:
            if analysis.pu_ratio > PU_OVERVALUED:
                signals.append(RiskFlag(
                    signal=RiskSignal.RED,
                    category="PU Ratio",
                    description=f"PU Ratio = {analysis.pu_ratio:.0f} (>100 = Sobrevaluado)",
                    severity=6.0,
                ))
            elif analysis.pu_ratio > PU_FAIR:
                signals.append(RiskFlag(
                    signal=RiskSignal.YELLOW,
                    category="PU Ratio",
                    description=f"PU Ratio = {analysis.pu_ratio:.0f} (valoracion justa)",
                    severity=3.0,
                ))
            else:
                signals.append(RiskFlag(
                    signal=RiskSignal.GREEN,
                    category="PU Ratio",
                    description=f"PU Ratio = {analysis.pu_ratio:.0f} (<60 = Infravaluado)",
                    severity=1.0,
                ))

        return signals

    def _compute_score(self, analysis: TokenomicsAnalysis) -> float:
        """Compute composite tokenomics score (0-100)."""
        score = 50.0

        # Distribution scoring (max +/- 20)
        insider_pct = analysis.distribution.insider_percentage
        if insider_pct <= 20:
            score += 20
        elif insider_pct <= 30:
            score += 10
        elif insider_pct <= 50:
            score -= 5
        else:
            score -= 20

        # Inflation scoring (max +/- 15)
        max_inf = analysis.inflation.max_inflation
        if max_inf < 20:
            score += 15
        elif max_inf < 50:
            score += 5
        elif max_inf < 100:
            score -= 5
        else:
            score -= 15

        # Vesting scoring (max +/- 10)
        vesting = analysis.vesting.vesting_duration_months
        if vesting >= 48:
            score += 10
        elif vesting >= 24:
            score += 5
        elif vesting > 0:
            score -= 5
        else:
            score -= 10

        # Utility scoring (max +/- 10)
        if analysis.utility.has_real_demand:
            score += 10
        if analysis.utility.revenue_share:
            score += 5
        if analysis.utility.staking_is_inflationary and UtilityType.STAKING_INFLATIONARY in analysis.utility.utility_types:
            score -= 5

        # FDV ratio penalty
        if analysis.fdv_mcap_ratio > FDV_MCAP_HIGH_RISK:
            score -= 15
        elif analysis.fdv_mcap_ratio > FDV_MCAP_MODERATE_RISK:
            score -= 8

        return max(0, min(100, score))
