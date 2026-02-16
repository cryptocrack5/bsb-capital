"""
BSB Capital - Configuration Settings
API endpoints, thresholds, and scoring parameters.
"""

# ============================================================================
# API ENDPOINTS
# ============================================================================
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
GITHUB_API_URL = "https://api.github.com"
LUNARCRUSH_BASE_URL = "https://lunarcrush.com/api/v2"

# ============================================================================
# TOKENOMICS THRESHOLDS
# ============================================================================

# Insider allocation thresholds (percentage)
INSIDER_ALLOCATION_HIGH_RISK = 50.0  # >50% = Red flag
INSIDER_ALLOCATION_MODERATE_RISK = 30.0  # >30% = Yellow flag
INSIDER_ALLOCATION_LOW_RISK = 20.0  # <20% = Green

# Inflation thresholds
INFLATION_HIGH_RISK = 100.0  # >100% max inflation = Red
INFLATION_MODERATE_RISK = 50.0  # >50% = Yellow
INFLATION_LOW_RISK = 20.0  # <20% = Green

# Vesting thresholds (months)
VESTING_STRONG = 48  # 4+ years = Green
VESTING_MODERATE = 24  # 2-4 years = Yellow
VESTING_WEAK = 12  # <1 year = Red

# FDV/Market Cap ratio
FDV_MCAP_HIGH_RISK = 10.0  # FDV > 10x Market Cap = Red
FDV_MCAP_MODERATE_RISK = 5.0  # FDV > 5x = Yellow

# PU Ratio thresholds (Price/Utility)
PU_OVERVALUED = 100
PU_FAIR = 60
PU_UNDERVALUED = 30

# ============================================================================
# QUALITATIVE SCORING WEIGHTS
# ============================================================================

# Sentiment Analysis
SENTIMENT_WEIGHTS = {
    "social_volume": 0.20,
    "sentiment_score": 0.25,
    "engagement_rate": 0.15,
    "organic_ratio": 0.25,
    "momentum_delta": 0.15,
}

# Team Scoring
TEAM_WEIGHTS = {
    "experience_years": 0.15,
    "previous_exits": 0.20,
    "github_activity": 0.20,
    "team_size": 0.10,
    "transparency": 0.15,
    "track_record": 0.20,
}

# VC/Partnership Scoring
VC_WEIGHTS = {
    "vc_tier": 0.30,
    "num_institutional_backers": 0.15,
    "strategic_alignment": 0.20,
    "follow_on_investment": 0.15,
    "partnership_quality": 0.20,
}

# ============================================================================
# TECHNICAL ANALYSIS PARAMETERS
# ============================================================================

# RSI
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
RSI_DIVERGENCE_LOOKBACK = 14

# Bollinger Bands
BB_PERIOD = 20
BB_STD_DEV = 2.0
BB_SQUEEZE_THRESHOLD = 0.04  # Bandwidth < 4% = squeeze

# Moving Averages
MA_SHORT = 20
MA_MEDIUM = 50
MA_LONG = 200

# VWAP
VWAP_VOLUME_MULTIPLIER = 2.0  # Volume > 2x avg = significant

# ATR
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.0

# Choppiness Index
CHOP_PERIOD = 14
CHOP_TRENDING = 38.2  # Below = trending
CHOP_RANGING = 61.8  # Above = ranging

# GARCH Model
GARCH_P = 1
GARCH_Q = 1

# Volatility Regime Thresholds
VOL_REGIME_HIGH = 0.80  # 80th percentile
VOL_REGIME_LOW = 0.20  # 20th percentile

# ============================================================================
# RISK ASSESSMENT
# ============================================================================

# Overall score weights for final rating
FINAL_SCORE_WEIGHTS = {
    "tokenomics": 0.30,
    "qualitative": 0.25,
    "technical": 0.25,
    "risk": 0.20,
}

# Rating thresholds (0-100)
RATING_STRONG_BUY = 80
RATING_BUY = 65
RATING_NEUTRAL = 45
RATING_SELL = 30
# Below 30 = STRONG SELL
