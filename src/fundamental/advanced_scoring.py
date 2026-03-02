"""
BSB Capital - Advanced Scoring Framework
Institutional-grade multi-dimensional scoring based on academic research
and best practices from Multicoin Capital, Paradigm, a16z crypto.

Implements:
- 6-Dimensional Tokenomics Scoring (Supply, Distribution, Utility, Value Accrual, Governance, Vesting)
- Token Velocity Problem analysis (Kyle Samani / Multicoin)
- Real Yield vs Inflationary Yield calculation
- NVT Ratio estimation
- Metcalfe Value estimation
- veToken model detection
- Value accrual mechanism classification
- Red flag auto-disqualifiers
"""

import logging
from typing import Optional
from dataclasses import dataclass, field

from src.models.schemas import (
    TokenMarketData,
    TokenType,
    UtilityType,
    TokenomicsAnalysis,
    QualitativeAnalysis,
    TechnicalAnalysis,
    RiskAssessment,
    DistributionData,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ADVANCED SCORING DATA MODELS
# ============================================================================


@dataclass
class TokenomicsDimensionScores:
    """6-dimensional tokenomics scoring (each 1-5)."""
    supply_mechanics: float = 3.0
    supply_detail: str = ""
    distribution: float = 3.0
    distribution_detail: str = ""
    utility: float = 3.0
    utility_detail: str = ""
    value_accrual: float = 3.0
    value_accrual_detail: str = ""
    governance: float = 3.0
    governance_detail: str = ""
    vesting_unlocks: float = 3.0
    vesting_detail: str = ""
    weighted_score: float = 50.0  # 0-100


@dataclass
class QualitativeDimensionScores:
    """4-category qualitative scoring."""
    team: float = 50.0
    team_detail: str = ""
    product_market_fit: float = 50.0
    pmf_detail: str = ""
    ecosystem_partners: float = 50.0
    ecosystem_detail: str = ""
    competitive_moat: float = 50.0
    moat_detail: str = ""
    weighted_score: float = 50.0  # 0-100


@dataclass
class QuantitativeMetricScores:
    """On-chain quantitative scoring."""
    pf_ratio_score: float = 50.0
    pf_detail: str = ""
    ptvl_score: float = 50.0
    ptvl_detail: str = ""
    revenue_growth_score: float = 50.0
    revenue_detail: str = ""
    dau_growth_score: float = 50.0
    dau_detail: str = ""
    developer_activity_score: float = 50.0
    dev_detail: str = ""
    real_yield_score: float = 50.0
    yield_detail: str = ""
    smart_money_score: float = 50.0
    smart_money_detail: str = ""
    supply_concentration_score: float = 50.0
    concentration_detail: str = ""
    weighted_score: float = 50.0  # 0-100


@dataclass
class VelocityAnalysis:
    """Token Velocity Problem analysis (Kyle Samani framework)."""
    estimated_velocity: float = 0.0
    velocity_sinks: list[str] = field(default_factory=list)
    velocity_risk: str = "medium"  # low, medium, high, critical
    has_staking_sink: bool = False
    has_burn_sink: bool = False
    has_governance_sink: bool = False
    has_revenue_sink: bool = False
    detail: str = ""


@dataclass
class RealYieldAnalysis:
    """Real Yield vs Inflationary Yield analysis."""
    estimated_protocol_revenue: float = 0.0
    estimated_token_emissions_value: float = 0.0
    real_yield_pct: Optional[float] = None
    is_real_yield: bool = False
    yield_sustainability: str = "unknown"  # sustainable, marginal, unsustainable, unknown
    detail: str = ""


@dataclass
class ValueAccrualAnalysis:
    """Value accrual mechanism analysis."""
    mechanisms: list[str] = field(default_factory=list)
    accrual_model: str = "none"  # burn, revenue_share, ve_token, hybrid, none
    fee_capture: bool = False
    buyback_burn: bool = False
    revenue_sharing: bool = False
    ve_token_model: bool = False
    work_token_model: bool = False
    detail: str = ""


@dataclass
class RedFlagAssessment:
    """Auto-disqualifier red flags."""
    triggered: list[str] = field(default_factory=list)
    is_disqualified: bool = False
    detail: str = ""


@dataclass
class AdvancedScoring:
    """Complete advanced scoring result."""
    tokenomics_dimensions: TokenomicsDimensionScores = field(
        default_factory=TokenomicsDimensionScores
    )
    qualitative_dimensions: QualitativeDimensionScores = field(
        default_factory=QualitativeDimensionScores
    )
    quantitative_metrics: QuantitativeMetricScores = field(
        default_factory=QuantitativeMetricScores
    )
    velocity: VelocityAnalysis = field(default_factory=VelocityAnalysis)
    real_yield: RealYieldAnalysis = field(default_factory=RealYieldAnalysis)
    value_accrual: ValueAccrualAnalysis = field(default_factory=ValueAccrualAnalysis)
    red_flags: RedFlagAssessment = field(default_factory=RedFlagAssessment)
    composite_score: float = 50.0
    conviction_tier: str = "Especulativo"
    # MV=PQ, NVT, Metcalfe estimations
    nvt_ratio: Optional[float] = None
    nvt_signal: str = ""
    metcalfe_value_ratio: Optional[float] = None
    metcalfe_signal: str = ""


# ============================================================================
# ADVANCED SCORING ENGINE
# ============================================================================


class AdvancedScoringEngine:
    """
    Institutional-grade scoring engine implementing frameworks from:
    - Multicoin Capital (Token Velocity, Real Yield, thesis-driven)
    - a16z crypto (PMF metrics, developer ecosystem)
    - Paradigm (technical depth, mechanism design)
    - Tim Roughgarden (incentive compatibility)
    - Token Terminal (financial metrics standardization)
    """

    # Weights from the integrated framework
    TOKENOMICS_WEIGHTS = {
        "supply_mechanics": 0.20,
        "distribution": 0.20,
        "utility": 0.20,
        "value_accrual": 0.15,
        "governance": 0.10,
        "vesting_unlocks": 0.15,
    }

    QUALITATIVE_WEIGHTS = {
        "team": 0.25,
        "product_market_fit": 0.30,
        "ecosystem_partners": 0.20,
        "competitive_moat": 0.25,
    }

    QUANTITATIVE_WEIGHTS = {
        "pf_ratio": 0.15,
        "ptvl": 0.10,
        "revenue_growth": 0.15,
        "dau_growth": 0.10,
        "developer_activity": 0.10,
        "real_yield": 0.15,
        "smart_money": 0.10,
        "supply_concentration": 0.15,
    }

    COMPOSITE_WEIGHTS = {
        "tokenomics": 0.30,
        "qualitative": 0.35,
        "quantitative": 0.35,
    }

    def compute(
        self,
        token: TokenMarketData,
        community_data: dict,
        tokenomics: TokenomicsAnalysis,
        qualitative: QualitativeAnalysis,
        technical: TechnicalAnalysis,
        risk: RiskAssessment,
    ) -> AdvancedScoring:
        result = AdvancedScoring()

        # 1. Velocity analysis
        result.velocity = self._analyze_velocity(token, community_data, tokenomics)

        # 2. Real Yield analysis
        result.real_yield = self._analyze_real_yield(token, tokenomics)

        # 3. Value Accrual analysis
        result.value_accrual = self._analyze_value_accrual(
            token, community_data, tokenomics
        )

        # 4. NVT and Metcalfe estimations
        result.nvt_ratio, result.nvt_signal = self._estimate_nvt(token)
        result.metcalfe_value_ratio, result.metcalfe_signal = (
            self._estimate_metcalfe(token, community_data)
        )

        # 5. Red flag assessment (auto-disqualifiers)
        result.red_flags = self._assess_red_flags(token, tokenomics)

        # 6. Six-dimensional tokenomics scoring
        result.tokenomics_dimensions = self._score_tokenomics_dimensions(
            token, tokenomics, result
        )

        # 7. Four-category qualitative scoring
        result.qualitative_dimensions = self._score_qualitative_dimensions(
            token, qualitative, tokenomics, community_data, result
        )

        # 8. Quantitative metrics scoring
        result.quantitative_metrics = self._score_quantitative_metrics(
            token, community_data, tokenomics, qualitative, technical, result
        )

        # 9. Composite score
        result.composite_score = (
            self.COMPOSITE_WEIGHTS["tokenomics"]
            * result.tokenomics_dimensions.weighted_score
            + self.COMPOSITE_WEIGHTS["qualitative"]
            * result.qualitative_dimensions.weighted_score
            + self.COMPOSITE_WEIGHTS["quantitative"]
            * result.quantitative_metrics.weighted_score
        )

        # Apply red flag penalty
        if result.red_flags.is_disqualified:
            result.composite_score = min(result.composite_score, 39.0)

        result.composite_score = max(0, min(100, result.composite_score))

        # Conviction tier
        if result.composite_score >= 80:
            result.conviction_tier = "Alta Conviccion"
        elif result.composite_score >= 60:
            result.conviction_tier = "Inversion Potencial"
        elif result.composite_score >= 40:
            result.conviction_tier = "Especulativo"
        else:
            result.conviction_tier = "No Invertir"

        return result

    # ------------------------------------------------------------------
    # VELOCITY ANALYSIS
    # ------------------------------------------------------------------

    def _analyze_velocity(
        self,
        token: TokenMarketData,
        community_data: dict,
        tokenomics: TokenomicsAnalysis,
    ) -> VelocityAnalysis:
        """
        Analyze Token Velocity Problem (Kyle Samani, Multicoin Capital).
        Network Value = Transaction Volume / Velocity
        High velocity => low network value per unit of transaction volume.
        """
        va = VelocityAnalysis()
        desc = community_data.get("description", "").lower()

        # Estimate velocity from volume/mcap ratio
        if token.market_cap > 0 and token.volume_24h > 0:
            annualized_vol = token.volume_24h * 365
            va.estimated_velocity = annualized_vol / token.market_cap
        else:
            va.estimated_velocity = 0

        # Detect velocity sinks
        if any(kw in desc for kw in ["staking", "stake", "proof-of-stake", "validator"]):
            va.velocity_sinks.append("Staking (bloqueo de supply)")
            va.has_staking_sink = True

        if any(kw in desc for kw in ["burn", "quema", "eip-1559", "deflation"]):
            va.velocity_sinks.append("Mecanismo de quema (burn)")
            va.has_burn_sink = True

        if any(kw in desc for kw in ["governance", "vote", "dao", "gobernanza"]):
            va.velocity_sinks.append("Gobernanza (incentivo de retencion)")
            va.has_governance_sink = True

        if any(
            kw in desc
            for kw in [
                "revenue",
                "fee share",
                "dividend",
                "real yield",
                "revenue sharing",
            ]
        ):
            va.velocity_sinks.append("Revenue sharing (profit-sharing sink)")
            va.has_revenue_sink = True

        if tokenomics.utility.revenue_share:
            if "Revenue sharing" not in str(va.velocity_sinks):
                va.velocity_sinks.append("Revenue sharing detectado")
                va.has_revenue_sink = True

        # Classify velocity risk
        num_sinks = len(va.velocity_sinks)
        if num_sinks >= 3:
            va.velocity_risk = "low"
            va.detail = (
                f"Velocidad estimada: {va.estimated_velocity:.1f}x. "
                f"{num_sinks} velocity sinks detectados - riesgo de velocidad bajo. "
                f"Multiples mecanismos de retencion reducen la presion de venta."
            )
        elif num_sinks >= 2:
            va.velocity_risk = "medium"
            va.detail = (
                f"Velocidad estimada: {va.estimated_velocity:.1f}x. "
                f"{num_sinks} velocity sinks - riesgo moderado. "
                f"Los sinks parcialmente mitigan el Token Velocity Problem."
            )
        elif num_sinks == 1:
            va.velocity_risk = "high"
            va.detail = (
                f"Velocidad estimada: {va.estimated_velocity:.1f}x. "
                f"Solo 1 velocity sink - riesgo alto. "
                f"Segun Samani (Multicoin), utility tokens sin sinks pueden alcanzar velocidades de 100-1000x."
            )
        else:
            va.velocity_risk = "critical"
            va.detail = (
                f"Velocidad estimada: {va.estimated_velocity:.1f}x. "
                f"Sin velocity sinks detectados - RIESGO CRITICO. "
                f"El Token Velocity Problem (Samani 2017) predice que sin mecanismos de retencion, "
                f"el valor de red permanece estancado independientemente del volumen de transacciones."
            )

        return va

    # ------------------------------------------------------------------
    # REAL YIELD ANALYSIS
    # ------------------------------------------------------------------

    def _analyze_real_yield(
        self, token: TokenMarketData, tokenomics: TokenomicsAnalysis
    ) -> RealYieldAnalysis:
        """
        Real Yield = (Protocol Revenue - Token Emissions Value) / Total Staked Value
        Post-Terra/Anchor (2022), this is the primary sustainability filter.
        GMX: ~4.3% APR real. Anchor: 20% APY entirely inflationary (collapsed).
        """
        ry = RealYieldAnalysis()

        # Estimate protocol revenue from volume
        # Typical fee rates: DEX ~0.3%, L1 ~0.01%, L2 ~0.005%
        if token.volume_24h > 0:
            if token.token_type == TokenType.DEFI:
                fee_rate = 0.003
            elif token.token_type == TokenType.L1:
                fee_rate = 0.0001
            elif token.token_type == TokenType.L2:
                fee_rate = 0.00005
            else:
                fee_rate = 0.0005

            ry.estimated_protocol_revenue = token.volume_24h * fee_rate * 365

        # Estimate emissions value
        if token.circulating_supply > 0 and token.total_supply > 0:
            tokens_remaining = token.total_supply - token.circulating_supply
            if tokens_remaining > 0:
                # Assume ~25% of remaining tokens emitted per year
                annual_emission_tokens = tokens_remaining * 0.25
                ry.estimated_token_emissions_value = (
                    annual_emission_tokens * token.price_usd
                )

        # Calculate Real Yield
        if ry.estimated_protocol_revenue > 0 and token.market_cap > 0:
            staked_value = token.market_cap * 0.3  # Assume 30% staked
            if staked_value > 0:
                net_revenue = (
                    ry.estimated_protocol_revenue
                    - ry.estimated_token_emissions_value
                )
                ry.real_yield_pct = (net_revenue / staked_value) * 100
                ry.is_real_yield = ry.real_yield_pct > 0

        # Sustainability classification
        if ry.real_yield_pct is not None:
            if ry.real_yield_pct > 2:
                ry.yield_sustainability = "sustainable"
                ry.detail = (
                    f"Real Yield estimado: {ry.real_yield_pct:.1f}%. "
                    f"Revenue del protocolo ({_fmt_num(ry.estimated_protocol_revenue)}/ano) "
                    f"supera las emisiones ({_fmt_num(ry.estimated_token_emissions_value)}/ano). "
                    f"Modelo sostenible similar a GMX (~4.3% APR real)."
                )
            elif ry.real_yield_pct > 0:
                ry.yield_sustainability = "marginal"
                ry.detail = (
                    f"Real Yield estimado: {ry.real_yield_pct:.1f}%. "
                    f"Marginalmente positivo - revenue apenas supera emisiones. "
                    f"Requiere crecimiento de fees para sostenibilidad a largo plazo."
                )
            elif ry.real_yield_pct > -5:
                ry.yield_sustainability = "unsustainable"
                ry.detail = (
                    f"Real Yield estimado: {ry.real_yield_pct:.1f}%. "
                    f"NEGATIVO - las emisiones de tokens superan el revenue del protocolo. "
                    f"Yield inflacionario insostenible (leccion de Terra/Anchor 2022)."
                )
            else:
                ry.yield_sustainability = "unsustainable"
                ry.detail = (
                    f"Real Yield estimado: {ry.real_yield_pct:.1f}%. "
                    f"Fuertemente negativo - el 85% de tokens lanzados en 2025 cotizan "
                    f"por debajo de su precio de emision por esta razon."
                )
        else:
            ry.yield_sustainability = "unknown"
            ry.detail = (
                "No se pudo estimar Real Yield por datos insuficientes. "
                "Sin mecanismo de revenue sharing verificable."
            )

        return ry

    # ------------------------------------------------------------------
    # VALUE ACCRUAL ANALYSIS
    # ------------------------------------------------------------------

    def _analyze_value_accrual(
        self,
        token: TokenMarketData,
        community_data: dict,
        tokenomics: TokenomicsAnalysis,
    ) -> ValueAccrualAnalysis:
        """
        Classify value accrual mechanisms:
        - Burns (Uniswap UNI, EIP-1559 ETH)
        - Revenue sharing to stakers (GMX, Ethena)
        - Vote-escrow + bribes (Curve, Aerodrome)
        - Work Token model (Filecoin concept)
        - Hybrid
        """
        va = ValueAccrualAnalysis()
        desc = community_data.get("description", "").lower()

        # Detect mechanisms
        if any(
            kw in desc for kw in ["burn", "quema", "eip-1559", "deflation", "deflationary"]
        ):
            va.mechanisms.append("Token burn / deflacion")
            va.buyback_burn = True
            va.fee_capture = True

        if any(
            kw in desc
            for kw in ["revenue sharing", "fee share", "dividend", "real yield"]
        ):
            va.mechanisms.append("Revenue sharing a stakers")
            va.revenue_sharing = True
            va.fee_capture = True

        if tokenomics.utility.revenue_share:
            if "Revenue sharing" not in str(va.mechanisms):
                va.mechanisms.append("Revenue sharing detectado")
                va.revenue_sharing = True
                va.fee_capture = True

        if any(kw in desc for kw in ["ve", "vote-escrow", "velodrome", "gauge"]):
            va.mechanisms.append("Modelo veToken (vote-escrow)")
            va.ve_token_model = True
            va.fee_capture = True

        if any(
            kw in desc for kw in ["work token", "filecoin", "mining reward", "compute"]
        ):
            va.mechanisms.append("Work Token model")
            va.work_token_model = True

        if any(kw in desc for kw in ["buyback", "recompra"]):
            va.mechanisms.append("Programa de buyback")
            va.buyback_burn = True

        # L1 tokens with staking + gas inherently accrue value
        if token.token_type == TokenType.L1:
            if "Gas/Fee token" not in str(va.mechanisms):
                va.mechanisms.append("Gas token (demanda intrinseca por uso de red)")
                va.fee_capture = True

        # Classify model
        active_models = sum(
            [va.buyback_burn, va.revenue_sharing, va.ve_token_model, va.work_token_model]
        )
        if active_models >= 2:
            va.accrual_model = "hybrid"
        elif va.revenue_sharing:
            va.accrual_model = "revenue_share"
        elif va.buyback_burn:
            va.accrual_model = "burn"
        elif va.ve_token_model:
            va.accrual_model = "ve_token"
        elif va.work_token_model:
            va.accrual_model = "work_token"
        else:
            va.accrual_model = "none"

        # Build detail
        if va.mechanisms:
            va.detail = (
                f"Mecanismos de acumulacion de valor: {'; '.join(va.mechanisms)}. "
                f"Modelo: {va.accrual_model}. "
            )
            if va.fee_capture:
                va.detail += (
                    "El token captura fees del protocolo, "
                    "alineando incentivos con el crecimiento del ecosistema."
                )
        else:
            va.detail = (
                "Sin mecanismos claros de acumulacion de valor detectados. "
                "El token puede sufrir del Token Velocity Problem - "
                "sin incentivo para retener, los usuarios compran, usan y venden inmediatamente."
            )

        return va

    # ------------------------------------------------------------------
    # NVT & METCALFE ESTIMATIONS
    # ------------------------------------------------------------------

    def _estimate_nvt(
        self, token: TokenMarketData
    ) -> tuple[Optional[float], str]:
        """
        NVT Ratio = Market Cap / Daily On-Chain Tx Volume (Willy Woo, 2017).
        High NVT = overvaluation; Low NVT = undervaluation.
        """
        if token.market_cap <= 0 or token.volume_24h <= 0:
            return None, ""

        # Use trading volume as proxy for on-chain volume
        # In reality, ~30%+ of volume may be inter-exchange transfers
        estimated_onchain = token.volume_24h * 0.7
        nvt = token.market_cap / estimated_onchain

        if nvt > 150:
            signal = (
                f"NVT = {nvt:.0f} - MUY ALTO. Capitalizacion excede significativamente "
                f"la utilidad transaccional. Posible sobrevaloración o narrativa store-of-value."
            )
        elif nvt > 80:
            signal = (
                f"NVT = {nvt:.0f} - ALTO. Ratio elevado sugiere que el precio incorpora "
                f"prima significativa sobre la utilidad transaccional."
            )
        elif nvt > 30:
            signal = (
                f"NVT = {nvt:.0f} - NORMAL. Ratio saludable entre capitalizacion y actividad de red."
            )
        else:
            signal = (
                f"NVT = {nvt:.0f} - BAJO. Alta actividad transaccional relativa a capitalizacion. "
                f"Posible infravaloración."
            )

        return round(nvt, 1), signal

    def _estimate_metcalfe(
        self, token: TokenMarketData, community_data: dict
    ) -> tuple[Optional[float], str]:
        """
        Metcalfe's Law: V proportional to n^1.69-2.0 (Peterson 2018, Wheatley 2019).
        n = active users (proxied by community metrics).
        """
        community = community_data.get("community", {})
        twitter = community.get("twitter_followers", 0)
        reddit = community.get("reddit_subscribers", 0)
        telegram = community.get("telegram_channel_user_count", 0)

        # Estimated active users (social following as proxy)
        total_social = twitter + reddit + telegram
        if total_social <= 0 or token.market_cap <= 0:
            return None, ""

        # Assume ~10% of social followers are active users
        estimated_active = total_social * 0.1

        # Metcalfe value: k * n^1.69 (empirical exponent from Wheatley et al.)
        # We normalize against a baseline (Bitcoin-like)
        metcalfe_raw = estimated_active ** 1.69

        # Ratio: actual market cap / metcalfe-implied value
        # Higher ratio = overvalued relative to network size
        # We use a simple normalization factor
        if metcalfe_raw > 0:
            ratio = token.market_cap / (metcalfe_raw * 100)  # scaling factor
        else:
            return None, ""

        if ratio > 500:
            signal = (
                f"Ratio Metcalfe = {ratio:.0f} - Capitalización muy por encima del valor "
                f"implicado por la Ley de Metcalfe. Usuarios estimados: {estimated_active:,.0f}."
            )
        elif ratio > 100:
            signal = (
                f"Ratio Metcalfe = {ratio:.0f} - Premium moderado sobre valor de red. "
                f"Usuarios estimados: {estimated_active:,.0f}."
            )
        else:
            signal = (
                f"Ratio Metcalfe = {ratio:.0f} - Alineado con valor de red. "
                f"Usuarios estimados: {estimated_active:,.0f}."
            )

        return round(ratio, 1), signal

    # ------------------------------------------------------------------
    # RED FLAG AUTO-DISQUALIFIERS
    # ------------------------------------------------------------------

    def _assess_red_flags(
        self, token: TokenMarketData, tokenomics: TokenomicsAnalysis
    ) -> RedFlagAssessment:
        """
        Auto-disqualifiers from the integrated framework:
        - Team/insider allocation >30%
        - No vesting or lockups <12 months
        - Unlimited supply without burn
        - Concentrated ownership enabling manipulation
        - No clear utility beyond speculation
        - Token not required to use protocol
        """
        rf = RedFlagAssessment()

        # Insider allocation >30%
        if tokenomics.distribution.insider_percentage > 30:
            rf.triggered.append(
                f"Allocacion equipo/insiders = {tokenomics.distribution.insider_percentage:.1f}% "
                f"(umbral: 30%). 'Sin vesting = sin confianza. Si pueden vender antes de que "
                f"parpadees, tu eres la exit liquidity.'"
            )

        # No vesting or <12 months
        if tokenomics.vesting.vesting_duration_months < 12 and tokenomics.vesting.vesting_duration_months > 0:
            rf.triggered.append(
                f"Vesting = {tokenomics.vesting.vesting_duration_months} meses "
                f"(minimo recomendado: 12). Vesting corto permite extraccion temprana."
            )

        # Unlimited supply without burn
        if (
            token.max_supply is None
            and not tokenomics.vesting.has_burn_mechanism
        ):
            if token.token_type not in (TokenType.L1,):
                rf.triggered.append(
                    "Supply ilimitado sin mecanismo de quema. "
                    "Riesgo de dilucion perpetua sin contrapeso deflacionario."
                )

        # Extreme FDV/MCap
        if tokenomics.fdv_mcap_ratio > 8:
            rf.triggered.append(
                f"FDV/MCap = {tokenomics.fdv_mcap_ratio:.1f}x (umbral: 8x). "
                f"Sam Andrew ('The Fully Diluted Fallacy') advierte que ratios >8-10x "
                f"senalan emisiones masivas futuras."
            )

        # No utility
        if not tokenomics.utility.has_real_demand and UtilityType.NONE in tokenomics.utility.utility_types:
            rf.triggered.append(
                "Sin utilidad clara mas alla de especulacion. "
                "Token no requerido para usar el protocolo."
            )

        # Concentration (top 10 wallets)
        top10 = tokenomics.distribution.top_10_wallet_concentration
        if top10 is not None and top10 > 60:
            rf.triggered.append(
                f"Concentracion top-10 wallets = {top10:.1f}%. "
                f"Ownership concentrada habilita manipulacion de mercado."
            )

        rf.is_disqualified = len(rf.triggered) >= 2
        if rf.triggered:
            rf.detail = (
                f"{len(rf.triggered)} red flags criticas detectadas. "
                + ("DESCALIFICADO: multiples indicadores de riesgo extremo." if rf.is_disqualified else "Requiere investigacion adicional.")
            )
        else:
            rf.detail = "Sin red flags auto-descalificadoras detectadas."

        return rf

    # ------------------------------------------------------------------
    # 6-DIMENSIONAL TOKENOMICS SCORING
    # ------------------------------------------------------------------

    def _score_tokenomics_dimensions(
        self,
        token: TokenMarketData,
        tokenomics: TokenomicsAnalysis,
        advanced: AdvancedScoring,
    ) -> TokenomicsDimensionScores:
        """
        Score Tokenomics on 6 dimensions (1-5 each):
        Supply Mechanics (20%), Distribution (20%), Utility (20%),
        Value Accrual (15%), Governance (10%), Vesting (15%)
        """
        td = TokenomicsDimensionScores()

        # --- Supply Mechanics (20%) ---
        score = 3.0
        details = []
        if token.max_supply is not None:
            score += 0.5
            details.append("Max supply definido")
        supply_ratio = tokenomics.inflation.supply_ratio * 100
        if supply_ratio > 70:
            score += 1.0
            details.append(f"Supply circulante alto ({supply_ratio:.0f}%)")
        elif supply_ratio > 30:
            details.append(f"Supply circulante moderado ({supply_ratio:.0f}%)")
        else:
            score -= 1.0
            details.append(f"Supply circulante bajo ({supply_ratio:.0f}%)")
        if tokenomics.vesting.has_burn_mechanism:
            score += 0.5
            details.append("Mecanismo de burn activo")
        if tokenomics.inflation.max_inflation > 100:
            score -= 1.0
            details.append(f"Inflacion maxima alta ({tokenomics.inflation.max_inflation:.0f}%)")
        td.supply_mechanics = max(1, min(5, score))
        td.supply_detail = ". ".join(details)

        # --- Distribution (20%) ---
        score = 3.0
        details = []
        insider = tokenomics.distribution.insider_percentage
        community = tokenomics.distribution.community_percentage
        if insider <= 20:
            score += 1.5
            details.append(f"Insiders bajo ({insider:.0f}%) - distribucion ideal")
        elif insider <= 30:
            score += 0.5
            details.append(f"Insiders moderado ({insider:.0f}%)")
        else:
            score -= 1.0
            details.append(f"Insiders alto ({insider:.0f}%) - riesgo de concentracion")
        if community >= 40:
            score += 0.5
            details.append(f"Comunidad >40% ({community:.0f}%)")
        td.distribution = max(1, min(5, score))
        td.distribution_detail = ". ".join(details)

        # --- Utility (20%) ---
        score = 3.0
        details = []
        utility_count = len(
            [u for u in tokenomics.utility.utility_types if u != UtilityType.NONE]
        )
        if utility_count >= 3:
            score += 1.5
            details.append(f"{utility_count} tipos de utilidad detectados")
        elif utility_count >= 2:
            score += 0.5
            details.append(f"{utility_count} tipos de utilidad")
        elif utility_count == 0:
            score -= 2.0
            details.append("Sin utilidad clara")
        if tokenomics.utility.has_real_demand:
            score += 0.5
            details.append("Demanda intrinseca real")
        if tokenomics.utility.gas_token:
            details.append("Gas token (demanda por uso)")
        td.utility = max(1, min(5, score))
        td.utility_detail = ". ".join(details)

        # --- Value Accrual (15%) ---
        score = 2.0
        details = []
        va = advanced.value_accrual
        if va.fee_capture:
            score += 1.0
            details.append("Captura de fees del protocolo")
        if va.buyback_burn:
            score += 0.5
            details.append("Buyback/burn activo")
        if va.revenue_sharing:
            score += 1.0
            details.append("Revenue sharing a holders")
        if va.ve_token_model:
            score += 0.5
            details.append("Modelo veToken")
        ry = advanced.real_yield
        if ry.is_real_yield:
            score += 0.5
            details.append(f"Real Yield positivo ({ry.real_yield_pct:.1f}%)")
        elif ry.real_yield_pct is not None and ry.real_yield_pct < 0:
            score -= 0.5
            details.append("Yield inflacionario (negativo)")
        if not details:
            details.append("Sin mecanismos de acumulacion de valor claros")
        td.value_accrual = max(1, min(5, score))
        td.value_accrual_detail = ". ".join(details)

        # --- Governance (10%) ---
        score = 3.0
        details = []
        if tokenomics.utility.governance_active:
            score += 1.0
            details.append("Gobernanza activa")
        else:
            score -= 0.5
            details.append("Sin gobernanza activa detectada")
        # Voting participation typically ~6.3% (Cong et al. 2025)
        details.append(
            "Nota: participacion promedio en gobernanza crypto es ~6.3% (Cong et al. 2025)"
        )
        td.governance = max(1, min(5, score))
        td.governance_detail = ". ".join(details)

        # --- Vesting & Unlocks (15%) ---
        score = 3.0
        details = []
        vesting = tokenomics.vesting.vesting_duration_months
        cliff = tokenomics.vesting.cliff_months
        if vesting >= 48 and cliff >= 12:
            score += 2.0
            details.append(f"Vesting {vesting}m con cliff {cliff}m - excelente")
        elif vesting >= 36:
            score += 1.0
            details.append(f"Vesting {vesting}m - solido")
        elif vesting >= 24:
            details.append(f"Vesting {vesting}m - aceptable")
        elif vesting > 0:
            score -= 1.0
            details.append(f"Vesting corto {vesting}m - riesgo de dump")
        else:
            score -= 1.5
            details.append("Sin vesting detectado")
        fdv_ratio = tokenomics.fdv_mcap_ratio
        if fdv_ratio < 3:
            score += 0.5
            details.append(f"FDV/MCap = {fdv_ratio:.1f}x - saludable")
        elif fdv_ratio > 5:
            score -= 0.5
            details.append(f"FDV/MCap = {fdv_ratio:.1f}x - dilucion futura")
        td.vesting_unlocks = max(1, min(5, score))
        td.vesting_detail = ". ".join(details)

        # --- Weighted score (0-100) ---
        w = self.TOKENOMICS_WEIGHTS
        raw = (
            w["supply_mechanics"] * td.supply_mechanics
            + w["distribution"] * td.distribution
            + w["utility"] * td.utility
            + w["value_accrual"] * td.value_accrual
            + w["governance"] * td.governance
            + w["vesting_unlocks"] * td.vesting_unlocks
        )
        # Scale from 1-5 to 0-100
        td.weighted_score = max(0, min(100, (raw - 1) / 4 * 100))

        return td

    # ------------------------------------------------------------------
    # 4-CATEGORY QUALITATIVE SCORING
    # ------------------------------------------------------------------

    def _score_qualitative_dimensions(
        self,
        token: TokenMarketData,
        qualitative: QualitativeAnalysis,
        tokenomics: TokenomicsAnalysis,
        community_data: dict,
        advanced: AdvancedScoring,
    ) -> QualitativeDimensionScores:
        """
        Score Qualitative on 4 categories (0-100 each):
        Team (25%), Product-Market Fit (30%), Ecosystem (20%), Competitive Moat (25%)
        """
        qd = QualitativeDimensionScores()

        # --- Team (25%) ---
        team = qualitative.team
        score = team.team_score
        details = []
        if team.founders_doxxed:
            details.append("Equipo doxxed")
        else:
            score = max(score - 10, 0)
            details.append("Equipo no doxxed - riesgo segun VCs institucionales")
        if team.development_activity_score > 60:
            details.append(f"Alta actividad de desarrollo ({team.development_activity_score:.0f}/100)")
        elif team.development_activity_score < 20:
            score = max(score - 15, 0)
            details.append("Actividad de desarrollo muy baja")
        if team.github_commits_30d > 100:
            details.append(f"{team.github_commits_30d} commits en 30d - shipping activo")
        qd.team = min(100, score)
        qd.team_detail = ". ".join(details) if details else "Datos de equipo limitados"

        # --- Product-Market Fit (30%) ---
        score = 50.0
        details = []
        # Revenue vs emissions
        ry = advanced.real_yield
        if ry.is_real_yield:
            score += 20
            details.append("Revenue > emisiones - PMF real")
        elif ry.real_yield_pct is not None and ry.real_yield_pct < 0:
            score -= 10
            details.append("Revenue < emisiones - protocolo subsidia actividad")

        # Organic ratio as proxy for real users vs farming
        if qualitative.sentiment.organic_ratio > 0.7:
            score += 15
            details.append(f"Alto ratio organico ({qualitative.sentiment.organic_ratio*100:.0f}%) - usuarios reales")
        elif qualitative.sentiment.organic_ratio < 0.3:
            score -= 15
            details.append("Bajo ratio organico - posible farming/manipulacion")

        # Hype index inversely correlates with sustainable PMF
        if qualitative.sentiment.hype_index > 80:
            score -= 10
            details.append("Hype excesivo - riesgo de burbuja")
        elif qualitative.sentiment.hype_index < 40:
            score += 5
            details.append("Hype bajo - crecimiento organico")

        # Utility demand
        if tokenomics.utility.has_real_demand:
            score += 10
            details.append("Token tiene demanda intrinseca real")

        qd.product_market_fit = max(0, min(100, score))
        qd.pmf_detail = ". ".join(details) if details else "Datos de PMF insuficientes"

        # --- Ecosystem/Partners (20%) ---
        vc = qualitative.vc
        score = vc.score
        details = []
        if vc.tier1_investors:
            score = max(score, 60)
            details.append(f"VC Tier-1: {', '.join(vc.tier1_investors[:3])}")
        if vc.strategic_partners:
            score += 10
            details.append(f"Partners estrategicos: {', '.join(vc.strategic_partners[:3])}")

        # Developer metrics from community data
        dev_data = community_data.get("developer", {})
        commits = dev_data.get("commit_count_4_weeks", 0)
        if commits > 200:
            score += 10
            details.append(f"{commits} commits/4w - ecosistema activo de developers")
        elif commits > 100:
            score += 5
            details.append(f"{commits} commits/4w")

        qd.ecosystem_partners = max(0, min(100, score))
        qd.ecosystem_detail = ". ".join(details) if details else "Datos de ecosistema limitados"

        # --- Competitive Moat (25%) ---
        score = 40.0
        details = []

        # Liquidity as moat (Mason Nystrom, Pantera)
        if token.volume_24h > 1e9:
            score += 20
            details.append("Liquidez profunda (vol >$1B/dia) - moat de liquidez")
        elif token.volume_24h > 100e6:
            score += 10
            details.append("Buena liquidez (vol >$100M/dia)")
        else:
            details.append("Liquidez limitada")

        # Network effects (market cap as proxy for network size)
        if token.market_cap > 100e9:
            score += 15
            details.append("Network effects fuertes (MCap >$100B)")
        elif token.market_cap > 10e9:
            score += 10
            details.append("Network effects en crecimiento")
        elif token.market_cap > 1e9:
            score += 5

        # Brand/Lindy effect
        categories = community_data.get("categories", [])
        if "Store of Value" in categories:
            score += 10
            details.append("Lindy Effect - narrativa store-of-value establecida")
        if token.token_type == TokenType.L1:
            score += 5
            details.append("L1 con ecosistema de developers")

        # Switching costs
        va = advanced.value_accrual
        if va.ve_token_model:
            score += 5
            details.append("veToken crea switching costs via lockups")

        # Alliance DAO rates best crypto at ~5/10 moat vs 10/10 for MSFT/AAPL
        details.append(
            "Nota: codigo open-source reduce moat vs. tech tradicional (Alliance DAO: ~5/10)"
        )

        qd.competitive_moat = max(0, min(100, score))
        qd.moat_detail = ". ".join(details)

        # --- Weighted score ---
        w = self.QUALITATIVE_WEIGHTS
        qd.weighted_score = (
            w["team"] * qd.team
            + w["product_market_fit"] * qd.product_market_fit
            + w["ecosystem_partners"] * qd.ecosystem_partners
            + w["competitive_moat"] * qd.competitive_moat
        )
        qd.weighted_score = max(0, min(100, qd.weighted_score))

        return qd

    # ------------------------------------------------------------------
    # QUANTITATIVE METRICS SCORING
    # ------------------------------------------------------------------

    def _score_quantitative_metrics(
        self,
        token: TokenMarketData,
        community_data: dict,
        tokenomics: TokenomicsAnalysis,
        qualitative: QualitativeAnalysis,
        technical: TechnicalAnalysis,
        advanced: AdvancedScoring,
    ) -> QuantitativeMetricScores:
        """
        Score on-chain quantitative metrics (0-100 each):
        P/F (15%), P/TVL (10%), Revenue Growth (15%), DAU Growth (10%),
        Developer Activity (10%), Real Yield (15%), Smart Money (10%),
        Supply Concentration (15%)
        """
        qm = QuantitativeMetricScores()

        # --- P/F Ratio vs peers (15%) ---
        pu = tokenomics.pu_ratio
        if pu is not None:
            if pu < 30:
                qm.pf_ratio_score = 90
                qm.pf_detail = f"P/F = {pu:.0f} - Muy bajo, posible infravaloración"
            elif pu < 60:
                qm.pf_ratio_score = 70
                qm.pf_detail = f"P/F = {pu:.0f} - Rango favorable"
            elif pu < 100:
                qm.pf_ratio_score = 50
                qm.pf_detail = f"P/F = {pu:.0f} - Valoracion justa"
            else:
                qm.pf_ratio_score = 25
                qm.pf_detail = f"P/F = {pu:.0f} - Elevado"
        else:
            qm.pf_ratio_score = 50
            qm.pf_detail = "P/F no disponible para este tipo de activo"

        # --- P/TVL Ratio (10%) ---
        # Estimate for DeFi tokens, otherwise neutral
        if token.token_type == TokenType.DEFI:
            # Estimated TVL based on market cap
            estimated_tvl = token.market_cap * 3  # DeFi typically TVL > MCap
            ptvl = token.market_cap / estimated_tvl if estimated_tvl > 0 else 1
            if ptvl < 0.5:
                qm.ptvl_score = 90
                qm.ptvl_detail = f"P/TVL = {ptvl:.2f} - Posible infravaloracion significativa"
            elif ptvl < 1.0:
                qm.ptvl_score = 70
                qm.ptvl_detail = f"P/TVL = {ptvl:.2f} - Favorable"
            else:
                qm.ptvl_score = 40
                qm.ptvl_detail = f"P/TVL = {ptvl:.2f} - Elevado"
        else:
            qm.ptvl_score = 50
            qm.ptvl_detail = "P/TVL no aplicable (no es DeFi)"

        # --- Revenue Growth (15%) ---
        # Proxy from price momentum
        if token.price_change_30d > 15:
            qm.revenue_growth_score = 80
            qm.revenue_detail = "Crecimiento fuerte reciente (+15% 30d) sugiere revenue creciente"
        elif token.price_change_30d > 0:
            qm.revenue_growth_score = 60
            qm.revenue_detail = "Crecimiento moderado"
        elif token.price_change_30d > -15:
            qm.revenue_growth_score = 40
            qm.revenue_detail = "Estancamiento o caida leve"
        else:
            qm.revenue_growth_score = 20
            qm.revenue_detail = f"Caida significativa ({token.price_change_30d:.1f}% 30d)"

        # --- DAU Growth (10%) ---
        community = community_data.get("community", {})
        active = community.get("reddit_accounts_active_48h", 0)
        subs = community.get("reddit_subscribers", 1)
        engagement = active / subs if subs > 0 else 0
        if engagement > 0.005:
            qm.dau_growth_score = 75
            qm.dau_detail = f"Alto engagement ({engagement*100:.1f}% activos/subs)"
        elif engagement > 0.002:
            qm.dau_growth_score = 55
            qm.dau_detail = f"Engagement moderado ({engagement*100:.2f}%)"
        else:
            qm.dau_growth_score = 35
            qm.dau_detail = "Bajo engagement de usuarios activos"

        # --- Developer Activity (10%) ---
        dev_data = community_data.get("developer", {})
        commits = dev_data.get("commit_count_4_weeks", 0)
        if commits > 200:
            qm.developer_activity_score = 90
            qm.dev_detail = f"{commits} commits/4sem - actividad excepcional"
        elif commits > 100:
            qm.developer_activity_score = 70
            qm.dev_detail = f"{commits} commits/4sem - buena actividad"
        elif commits > 30:
            qm.developer_activity_score = 50
            qm.dev_detail = f"{commits} commits/4sem - actividad moderada"
        else:
            qm.developer_activity_score = 25
            qm.dev_detail = f"{commits} commits/4sem - actividad baja"

        # --- Real Yield (15%) ---
        ry = advanced.real_yield
        if ry.real_yield_pct is not None:
            if ry.real_yield_pct > 5:
                qm.real_yield_score = 90
                qm.yield_detail = f"Real Yield = {ry.real_yield_pct:.1f}% - excelente"
            elif ry.real_yield_pct > 2:
                qm.real_yield_score = 75
                qm.yield_detail = f"Real Yield = {ry.real_yield_pct:.1f}% - sostenible"
            elif ry.real_yield_pct > 0:
                qm.real_yield_score = 55
                qm.yield_detail = f"Real Yield = {ry.real_yield_pct:.1f}% - marginal"
            else:
                qm.real_yield_score = 25
                qm.yield_detail = f"Real Yield = {ry.real_yield_pct:.1f}% - NEGATIVO"
        else:
            qm.real_yield_score = 40
            qm.yield_detail = "Real Yield no disponible"

        # --- Smart Money Flows (10%) ---
        # Proxy from VC quality and volume trends
        vc_score = qualitative.vc.score
        vol_trend = token.volume_24h / token.market_cap if token.market_cap > 0 else 0
        if vc_score > 70 and vol_trend > 0.03:
            qm.smart_money_score = 80
            qm.smart_money_detail = "Flujos Smart Money positivos (backing VC fuerte + volumen alto)"
        elif vc_score > 50:
            qm.smart_money_score = 60
            qm.smart_money_detail = "Flujos Smart Money neutrales"
        else:
            qm.smart_money_score = 40
            qm.smart_money_detail = "Datos de Smart Money limitados"

        # --- Supply Concentration (15%) ---
        top10 = tokenomics.distribution.top_10_wallet_concentration
        if top10 is not None:
            if top10 < 20:
                qm.supply_concentration_score = 90
                qm.concentration_detail = f"Top-10 = {top10:.0f}% - distribucion excelente"
            elif top10 < 30:
                qm.supply_concentration_score = 70
                qm.concentration_detail = f"Top-10 = {top10:.0f}% - favorable"
            elif top10 < 50:
                qm.supply_concentration_score = 50
                qm.concentration_detail = f"Top-10 = {top10:.0f}% - moderada"
            else:
                qm.supply_concentration_score = 25
                qm.concentration_detail = f"Top-10 = {top10:.0f}% - concentrada"
        else:
            qm.supply_concentration_score = 50
            qm.concentration_detail = "Datos de concentracion no disponibles"

        # --- Weighted score ---
        w = self.QUANTITATIVE_WEIGHTS
        qm.weighted_score = (
            w["pf_ratio"] * qm.pf_ratio_score
            + w["ptvl"] * qm.ptvl_score
            + w["revenue_growth"] * qm.revenue_growth_score
            + w["dau_growth"] * qm.dau_growth_score
            + w["developer_activity"] * qm.developer_activity_score
            + w["real_yield"] * qm.real_yield_score
            + w["smart_money"] * qm.smart_money_score
            + w["supply_concentration"] * qm.supply_concentration_score
        )
        qm.weighted_score = max(0, min(100, qm.weighted_score))

        return qm


# ============================================================================
# HELPERS
# ============================================================================


def _fmt_num(n: float) -> str:
    if n >= 1e12:
        return f"${n/1e12:.2f}T"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    if n >= 1e3:
        return f"${n/1e3:.0f}K"
    return f"${n:,.0f}"
