"""
BSB Capital - Data Models
Pydantic schemas for structured data throughout the analysis pipeline.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ============================================================================
# ENUMS
# ============================================================================

class TokenType(Enum):
    L1 = "Layer 1 / Moneda"
    L2 = "Layer 2"
    DEFI = "DeFi / dApp"
    INFRASTRUCTURE = "Infraestructura"
    GAMING = "Gaming / Metaverse"
    MEME = "Meme"
    STABLECOIN = "Stablecoin"
    UNKNOWN = "Desconocido"


class UtilityType(Enum):
    GAS = "Gas / Comisiones"
    GOVERNANCE = "Gobernanza"
    STAKING_REAL = "Staking Real (Dividendos)"
    STAKING_INFLATIONARY = "Staking Inflacionario"
    PAYMENTS = "Pagos"
    COLLATERAL = "Colateral"
    ACCESS = "Acceso a Servicios"
    NONE = "Sin Utilidad Clara"


class RiskSignal(Enum):
    RED = "ROJO"
    YELLOW = "AMARILLO"
    GREEN = "VERDE"


class Verdict(Enum):
    STRONG_BUY = "Fuertemente Alcista"
    BUY = "Alcista"
    NEUTRAL = "Neutral"
    SELL = "Bajista"
    STRONG_SELL = "Fuertemente Bajista"


class VolatilityRegime(Enum):
    LOW = "Baja Volatilidad"
    NORMAL = "Normal"
    HIGH = "Alta Volatilidad"
    EXTREME = "Volatilidad Extrema"


class TrendDirection(Enum):
    BULLISH = "Alcista"
    BEARISH = "Bajista"
    SIDEWAYS = "Lateral"


# ============================================================================
# TOKEN DATA
# ============================================================================

@dataclass
class TokenMarketData:
    """Raw market data for a token."""
    name: str
    symbol: str
    token_type: TokenType = TokenType.UNKNOWN
    price_usd: float = 0.0
    market_cap: float = 0.0
    fully_diluted_valuation: float = 0.0
    circulating_supply: float = 0.0
    total_supply: float = 0.0
    max_supply: Optional[float] = None
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    price_change_30d: float = 0.0
    ath: float = 0.0
    ath_change_percentage: float = 0.0
    atl: float = 0.0
    coingecko_id: str = ""


# ============================================================================
# TOKENOMICS (FUNDAMENTAL)
# ============================================================================

@dataclass
class DistributionData:
    """Token distribution breakdown."""
    team_allocation: float = 0.0  # percentage
    investor_allocation: float = 0.0
    community_allocation: float = 0.0
    ecosystem_allocation: float = 0.0
    treasury_allocation: float = 0.0
    foundation_allocation: float = 0.0
    airdrop_allocation: float = 0.0
    other_allocation: float = 0.0
    insider_percentage: float = 0.0  # team + investors
    community_percentage: float = 0.0  # community + ecosystem + airdrop
    gini_coefficient: Optional[float] = None
    top_10_wallet_concentration: Optional[float] = None
    data_available: bool = False


@dataclass
class VestingSchedule:
    """Vesting and emission schedule."""
    cliff_months: int = 0
    vesting_duration_months: int = 0
    tge_unlock_percentage: float = 0.0  # Token Generation Event unlock
    monthly_unlock_rate: float = 0.0
    next_major_unlock_date: str = ""
    next_major_unlock_amount: float = 0.0
    tokens_locked: float = 0.0
    tokens_unlocked: float = 0.0
    has_burn_mechanism: bool = False
    has_buyback_mechanism: bool = False
    data_available: bool = False


@dataclass
class InflationMetrics:
    """Inflation analysis."""
    current_inflation_rate: float = 0.0  # annualized
    max_inflation: float = 0.0  # (tokens_to_unlock / circulating)
    supply_ratio: float = 0.0  # circulating / total
    emission_schedule_type: str = ""  # "linear", "exponential_decay", "fixed"
    years_to_full_dilution: Optional[float] = None


@dataclass
class TokenUtility:
    """Token utility analysis."""
    utility_types: list[UtilityType] = field(default_factory=list)
    has_real_demand: bool = False
    staking_apy: Optional[float] = None
    staking_is_inflationary: bool = True
    revenue_share: bool = False
    real_yield_percentage: Optional[float] = None
    gas_token: bool = False
    governance_active: bool = False
    description: str = ""


@dataclass
class TokenomicsAnalysis:
    """Complete tokenomics analysis result."""
    distribution: DistributionData = field(default_factory=DistributionData)
    vesting: VestingSchedule = field(default_factory=VestingSchedule)
    inflation: InflationMetrics = field(default_factory=InflationMetrics)
    utility: TokenUtility = field(default_factory=TokenUtility)
    pu_ratio: Optional[float] = None
    fdv_mcap_ratio: float = 0.0
    score: float = 0.0  # 0-100
    risk_signals: list[RiskFlag] = field(default_factory=list)


# ============================================================================
# QUALITATIVE ANALYSIS
# ============================================================================

@dataclass
class SentimentAnalysis:
    """Market sentiment metrics."""
    overall_sentiment: float = 0.0  # -1 to 1
    social_volume_24h: int = 0
    social_volume_7d_avg: int = 0
    social_volume_trend: str = ""  # "increasing", "decreasing", "stable"
    twitter_sentiment: float = 0.0
    reddit_sentiment: float = 0.0
    news_sentiment: float = 0.0
    engagement_rate: float = 0.0
    organic_ratio: float = 0.0  # estimated organic vs. bot/paid
    hype_index: float = 0.0  # 0-100 composite
    galaxy_score: Optional[float] = None
    fear_greed_index: Optional[int] = None
    score: float = 0.0  # 0-100


@dataclass
class TeamAnalysis:
    """Team quality assessment."""
    founders_identified: bool = False
    founders_doxxed: bool = False
    team_size: int = 0
    avg_experience_years: float = 0.0
    previous_exits: int = 0
    previous_crypto_projects: int = 0
    github_contributors: int = 0
    github_commits_30d: int = 0
    github_commit_trend: str = ""  # "increasing", "decreasing", "stable"
    development_activity_score: float = 0.0  # 0-100
    transparency_score: float = 0.0  # 0-100
    track_record_score: float = 0.0  # 0-100
    team_score: float = 0.0  # 0-100 composite


@dataclass
class VCAnalysis:
    """VC and partnership analysis."""
    total_raised: float = 0.0
    num_funding_rounds: int = 0
    last_round_valuation: Optional[float] = None
    tier1_investors: list[str] = field(default_factory=list)
    tier2_investors: list[str] = field(default_factory=list)
    tier3_investors: list[str] = field(default_factory=list)
    strategic_partners: list[str] = field(default_factory=list)
    vc_reputation_score: float = 0.0  # 0-100
    partnership_quality_score: float = 0.0  # 0-100
    follow_on_investment: bool = False
    cap_table_health: float = 0.0  # 0-100
    score: float = 0.0  # 0-100 composite


@dataclass
class QualitativeAnalysis:
    """Complete qualitative analysis result."""
    sentiment: SentimentAnalysis = field(default_factory=SentimentAnalysis)
    team: TeamAnalysis = field(default_factory=TeamAnalysis)
    vc: VCAnalysis = field(default_factory=VCAnalysis)
    score: float = 0.0  # 0-100


# ============================================================================
# TECHNICAL ANALYSIS
# ============================================================================

@dataclass
class MomentumIndicators:
    """Technical momentum indicators."""
    rsi: float = 50.0
    rsi_signal: str = ""  # "overbought", "oversold", "neutral"
    rsi_divergence: Optional[str] = None  # "bullish", "bearish", None
    macd_value: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    macd_crossover: Optional[str] = None  # "bullish", "bearish"
    vwap: float = 0.0
    price_vs_vwap: str = ""  # "above", "below"
    vwap_volume_signal: bool = False
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_bandwidth: float = 0.0
    bb_squeeze: bool = False
    ma_20: float = 0.0
    ma_50: float = 0.0
    ma_200: float = 0.0
    golden_cross: bool = False
    death_cross: bool = False
    trend: TrendDirection = TrendDirection.SIDEWAYS
    score: float = 50.0  # 0-100


@dataclass
class VolatilityAnalysis:
    """Volatility and risk metrics."""
    atr: float = 0.0
    atr_percentage: float = 0.0
    historical_volatility_30d: float = 0.0
    implied_volatility: Optional[float] = None
    choppiness_index: float = 50.0
    market_regime: VolatilityRegime = VolatilityRegime.NORMAL
    garch_forecast: Optional[float] = None
    max_drawdown_30d: float = 0.0
    max_drawdown_90d: float = 0.0
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    dynamic_stop_loss: float = 0.0
    confidence_adjustment: float = 1.0  # 0-1, reduces in high vol
    score: float = 50.0  # 0-100 (higher = less risky)


@dataclass
class NewsImpactAnalysis:
    """News and event impact analysis."""
    recent_news_sentiment: float = 0.0  # -1 to 1
    significant_events: list[str] = field(default_factory=list)
    upcoming_catalysts: list[str] = field(default_factory=list)
    regulatory_risk: float = 0.0  # 0-100
    upcoming_unlocks: list[str] = field(default_factory=list)
    buy_rumor_sell_news_risk: float = 0.0  # 0-100
    news_volume_anomaly: bool = False
    score: float = 50.0  # 0-100


@dataclass
class TechnicalAnalysis:
    """Complete technical analysis result."""
    momentum: MomentumIndicators = field(default_factory=MomentumIndicators)
    volatility: VolatilityAnalysis = field(default_factory=VolatilityAnalysis)
    news_impact: NewsImpactAnalysis = field(default_factory=NewsImpactAnalysis)
    score: float = 50.0  # 0-100


# ============================================================================
# RISK ASSESSMENT
# ============================================================================

@dataclass
class RiskFlag:
    """Individual risk signal."""
    signal: RiskSignal
    category: str
    description: str
    severity: float = 0.0  # 0-10


@dataclass
class RiskAssessment:
    """Comprehensive risk assessment."""
    red_flags: list[RiskFlag] = field(default_factory=list)
    yellow_flags: list[RiskFlag] = field(default_factory=list)
    green_flags: list[RiskFlag] = field(default_factory=list)
    low_float_high_fdv: bool = False
    team_has_immediate_liquidity: bool = False
    mercenary_incentives: bool = False
    moral_hazard_risk: float = 0.0  # 0-100
    dumping_structure: bool = False
    overall_risk_score: float = 50.0  # 0-100 (higher = safer)


# ============================================================================
# FINAL REPORT
# ============================================================================

@dataclass
class AnalysisReport:
    """Complete analysis report for a token."""
    token: TokenMarketData = field(default_factory=TokenMarketData)
    tokenomics: TokenomicsAnalysis = field(default_factory=TokenomicsAnalysis)
    qualitative: QualitativeAnalysis = field(default_factory=QualitativeAnalysis)
    technical: TechnicalAnalysis = field(default_factory=TechnicalAnalysis)
    risk: RiskAssessment = field(default_factory=RiskAssessment)
    final_score: float = 50.0  # 0-100
    verdict: Verdict = Verdict.NEUTRAL
    analysis_timestamp: str = ""
    disclaimer: str = (
        "Este analisis es educativo y no constituye consejo financiero. "
        "Realice su propia investigacion antes de tomar decisiones de inversion."
    )
