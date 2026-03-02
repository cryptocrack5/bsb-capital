"""
BSB Capital - Web Dashboard
Flask application serving the analysis interface with
advanced institutional-grade scoring and investment memo generation.
"""

import sys
import os
import json
from dataclasses import asdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.schemas import (
    TokenMarketData, TokenType, AnalysisReport,
    QualitativeAnalysis, TechnicalAnalysis,
    DistributionData, Verdict, RiskSignal,
    VolatilityRegime, TrendDirection,
)
from src.fundamental.tokenomics import TokenomicsAnalyzer
from src.fundamental.advanced_scoring import AdvancedScoringEngine
from src.qualitative.sentiment import SentimentAnalyzer
from src.qualitative.team_scoring import TeamScorer
from src.qualitative.vc_analysis import VCAnalyzer
from src.technical.indicators import TechnicalIndicatorEngine
from src.technical.volatility import VolatilityEngine
from src.technical.news_impact import NewsImpactAnalyzer
from src.risk.risk_engine import RiskEngine
from src.core.memo_generator import MemoGenerator

app = Flask(__name__, template_folder="templates", static_folder="static")


class NumpyEncoder(json.JSONEncoder):
    """Handle numpy types in JSON serialization."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


app.json.encoder = NumpyEncoder  # type: ignore

# ============================================================================
# SAMPLE DATA
# ============================================================================

TOKENS = {
    "ethereum": {
        "token": TokenMarketData(
            name="Ethereum", symbol="ETH", token_type=TokenType.L1,
            price_usd=2_684.32, market_cap=323_500_000_000,
            fully_diluted_valuation=323_500_000_000,
            circulating_supply=120_520_000, total_supply=120_520_000,
            max_supply=None, volume_24h=14_200_000_000,
            price_change_24h=-0.83, price_change_7d=2.14, price_change_30d=-8.42,
            ath=4_878.26, ath_change_percentage=-44.97, atl=0.432979,
        ),
        "community": {
            "description": "Ethereum is a decentralized platform for smart contracts and dApps. It uses proof-of-stake consensus with real yield from staking. Features governance, gas token, EIP-1559 burn mechanism with revenue sharing.",
            "categories": ["Smart Contract Platform", "Layer 1"],
            "community": {"twitter_followers": 3_400_000, "reddit_subscribers": 2_800_000, "reddit_accounts_active_48h": 8_200, "telegram_channel_user_count": 85_000},
            "developer": {"commit_count_4_weeks": 320, "code_additions_deletions_4_weeks": {"additions": 12000, "deletions": 5500}},
            "links": {"homepage": ["https://ethereum.org"], "twitter_screen_name": "ethereum", "subreddit_url": "https://reddit.com/r/ethereum", "repos_url": {"github": ["https://github.com/ethereum/go-ethereum"]}},
        },
        "distribution": DistributionData(team_allocation=9.9, investor_allocation=16.5, community_allocation=50.0, ecosystem_allocation=13.6, foundation_allocation=5.0, treasury_allocation=5.0, insider_percentage=26.4, community_percentage=63.6, top_10_wallet_concentration=35.2, data_available=True),
        "founders": ["Vitalik Buterin"],
        "investors": ["Paradigm", "a16z", "Polychain Capital"],
        "partners": ["Microsoft", "JPMorgan", "Visa", "BlackRock"],
    },
    "bitcoin": {
        "token": TokenMarketData(
            name="Bitcoin", symbol="BTC", token_type=TokenType.L1,
            price_usd=97_432.15, market_cap=1_932_000_000_000,
            fully_diluted_valuation=2_046_000_000_000,
            circulating_supply=19_820_000, total_supply=21_000_000,
            max_supply=21_000_000, volume_24h=28_500_000_000,
            price_change_24h=1.24, price_change_7d=4.87, price_change_30d=-2.15,
            ath=109_114.88, ath_change_percentage=-10.7, atl=67.81,
        ),
        "community": {
            "description": "Bitcoin is a decentralized digital currency with no central bank. Peer-to-peer payments using proof-of-work consensus. Store of value and payment system.",
            "categories": ["Cryptocurrency", "Layer 1", "Store of Value"],
            "community": {"twitter_followers": 6_800_000, "reddit_subscribers": 5_200_000, "reddit_accounts_active_48h": 12_500, "telegram_channel_user_count": 120_000},
            "developer": {"commit_count_4_weeks": 180, "code_additions_deletions_4_weeks": {"additions": 4500, "deletions": 2100}},
            "links": {"homepage": ["https://bitcoin.org"], "twitter_screen_name": "bitcoin", "subreddit_url": "https://reddit.com/r/bitcoin", "repos_url": {"github": ["https://github.com/bitcoin/bitcoin"]}},
        },
        "distribution": DistributionData(team_allocation=0.0, investor_allocation=0.0, community_allocation=100.0, insider_percentage=0.0, community_percentage=100.0, data_available=True),
        "founders": ["Satoshi Nakamoto"],
        "investors": [],
        "partners": ["Lightning Network", "MicroStrategy", "BlackRock"],
    },
    "solana": {
        "token": TokenMarketData(
            name="Solana", symbol="SOL", token_type=TokenType.L1,
            price_usd=193.47, market_cap=94_200_000_000,
            fully_diluted_valuation=113_800_000_000,
            circulating_supply=486_900_000, total_supply=588_200_000,
            max_supply=None, volume_24h=3_100_000_000,
            price_change_24h=2.31, price_change_7d=8.67, price_change_30d=-12.53,
            ath=293.31, ath_change_percentage=-34.03, atl=0.50052,
        ),
        "community": {
            "description": "Solana is a high-performance Layer 1 blockchain with smart contracts, DeFi, proof-of-stake and proof-of-history. SOL is gas token for fees and staking.",
            "categories": ["Smart Contract Platform", "Layer 1", "DeFi"],
            "community": {"twitter_followers": 2_900_000, "reddit_subscribers": 320_000, "reddit_accounts_active_48h": 3_800, "telegram_channel_user_count": 45_000},
            "developer": {"commit_count_4_weeks": 250, "code_additions_deletions_4_weeks": {"additions": 8500, "deletions": 3200}},
            "links": {"homepage": ["https://solana.com"], "twitter_screen_name": "solana", "repos_url": {"github": ["https://github.com/solana-labs/solana"]}},
        },
        "distribution": DistributionData(team_allocation=12.8, investor_allocation=24.2, community_allocation=38.9, ecosystem_allocation=14.1, foundation_allocation=10.0, insider_percentage=37.0, community_percentage=53.0, data_available=True),
        "founders": ["Anatoly Yakovenko"],
        "investors": ["a16z", "Polychain Capital", "Multicoin Capital", "Jump Crypto"],
        "partners": ["Google Cloud", "Visa"],
    },
    "arbitrum": {
        "token": TokenMarketData(
            name="Arbitrum", symbol="ARB", token_type=TokenType.L2,
            price_usd=0.3821, market_cap=1_530_000_000,
            fully_diluted_valuation=3_820_000_000,
            circulating_supply=4_006_000_000, total_supply=10_000_000_000,
            max_supply=10_000_000_000, volume_24h=285_000_000,
            price_change_24h=-1.45, price_change_7d=-5.23, price_change_30d=-18.67,
            ath=2.39, ath_change_percentage=-84.01, atl=0.3445,
        ),
        "community": {
            "description": "Arbitrum is Layer 2 scaling for Ethereum using optimistic rollups. ARB is governance token for DAO voting.",
            "categories": ["Layer 2", "Scaling", "Optimistic Rollup"],
            "community": {"twitter_followers": 980_000, "reddit_subscribers": 85_000, "reddit_accounts_active_48h": 1_200, "telegram_channel_user_count": 32_000},
            "developer": {"commit_count_4_weeks": 145, "code_additions_deletions_4_weeks": {"additions": 5200, "deletions": 2800}},
            "links": {"homepage": ["https://arbitrum.io"], "twitter_screen_name": "arbitrum", "repos_url": {"github": ["https://github.com/OffchainLabs/nitro"]}},
        },
        "distribution": DistributionData(team_allocation=26.9, investor_allocation=17.5, community_allocation=11.6, ecosystem_allocation=1.1, treasury_allocation=42.8, airdrop_allocation=11.6, insider_percentage=44.4, community_percentage=24.3, data_available=True),
        "founders": [],
        "investors": ["Pantera Capital", "Lightspeed", "Polychain Capital"],
        "partners": [],
    },
}


def generate_ohlcv(key: str, days=300):
    np.random.seed(hash(key) % 2**31)
    t = TOKENS[key]["token"]
    start = t.price_usd * np.random.uniform(0.6, 1.4)
    trend = np.linspace(0, np.log(t.price_usd / start), days)
    noise = np.cumsum(np.random.randn(days) * 0.025)
    close = np.exp(np.log(start) + trend + noise)
    vol_noise = np.abs(np.random.randn(days)) * close * 0.02
    return pd.DataFrame({
        "open": close + np.random.randn(days) * close * 0.005,
        "high": close + vol_noise,
        "low": close - vol_noise,
        "close": close,
        "volume": t.volume_24h * np.exp(np.random.randn(days) * 0.5),
    }, index=pd.date_range(end=datetime.now(), periods=days, freq="D"))


def _run_base_analysis(key: str):
    """Run base analysis and return intermediate objects for reuse."""
    d = TOKENS[key]
    token = d["token"]
    community = d["community"]

    tok_a = TokenomicsAnalyzer()
    tok_result = tok_a.analyze(token, community, distribution_override=d.get("distribution"))

    sent_a = SentimentAnalyzer()
    vr = token.volume_24h / (token.market_cap * 0.01) if token.market_cap else 1
    sentiment = sent_a.analyze(community, token.name, price_change_7d=token.price_change_7d, volume_change_ratio=min(5, vr))

    team_a = TeamScorer()
    team = team_a.analyze(community, known_founders=d.get("founders"))

    vc_a = VCAnalyzer()
    vc = vc_a.analyze(token.name, known_investors=d.get("investors"), known_partners=d.get("partners"))

    qual = QualitativeAnalysis(sentiment=sentiment, team=team, vc=vc, score=sentiment.score*0.35+team.team_score*0.35+vc.score*0.30)

    ohlcv = generate_ohlcv(key)
    mom = TechnicalIndicatorEngine().analyze(ohlcv)
    volat = VolatilityEngine().analyze(ohlcv)
    news = NewsImpactAnalyzer().analyze(token.name, description=community.get("description",""), has_upcoming_unlocks=tok_result.inflation.max_inflation>30, inflation_rate=tok_result.inflation.max_inflation)
    tech = TechnicalAnalysis(momentum=mom, volatility=volat, news_impact=news, score=mom.score*0.45+volat.score*0.35+news.score*0.20)

    risk_eng = RiskEngine()
    risk = risk_eng.assess(tok_result, qual, tech)
    final_score, verdict = risk_eng.compute_verdict(tok_result, qual, tech, risk)

    # Advanced scoring
    adv_engine = AdvancedScoringEngine()
    advanced = adv_engine.compute(token, community, tok_result, qual, tech, risk)

    return {
        "token": token,
        "community": community,
        "tok_result": tok_result,
        "sentiment": sentiment,
        "team": team,
        "vc": vc,
        "qual": qual,
        "tech": tech,
        "mom": mom,
        "volat": volat,
        "risk": risk,
        "final_score": final_score,
        "verdict": verdict,
        "ohlcv": ohlcv,
        "advanced": advanced,
    }


def run_analysis(key: str) -> dict:
    base = _run_base_analysis(key)
    token = base["token"]
    tok_result = base["tok_result"]
    sentiment = base["sentiment"]
    team = base["team"]
    vc = base["vc"]
    qual = base["qual"]
    tech = base["tech"]
    mom = base["mom"]
    volat = base["volat"]
    risk = base["risk"]
    final_score = base["final_score"]
    verdict = base["verdict"]
    ohlcv = base["ohlcv"]
    advanced = base["advanced"]

    # Build price history for chart
    prices = ohlcv["close"].tolist()
    dates = [d.strftime("%Y-%m-%d") for d in ohlcv.index]

    def fmt_num(n):
        if n >= 1e12: return f"${n/1e12:.2f}T"
        if n >= 1e9: return f"${n/1e9:.2f}B"
        if n >= 1e6: return f"${n/1e6:.1f}M"
        return f"${n:,.0f}"

    def fmt_price(p):
        if p < 0.01: return f"${p:.6f}"
        if p < 1: return f"${p:.4f}"
        return f"${p:,.2f}"

    td = advanced.tokenomics_dimensions
    qd = advanced.qualitative_dimensions
    qm = advanced.quantitative_metrics

    return {
        "token": {
            "name": token.name, "symbol": token.symbol,
            "type": token.token_type.value,
            "price": fmt_price(token.price_usd), "price_raw": token.price_usd,
            "market_cap": fmt_num(token.market_cap), "market_cap_raw": token.market_cap,
            "fdv": fmt_num(token.fully_diluted_valuation),
            "volume_24h": fmt_num(token.volume_24h),
            "circulating": f"{token.circulating_supply:,.0f}",
            "total_supply": f"{token.total_supply:,.0f}",
            "change_24h": token.price_change_24h,
            "change_7d": token.price_change_7d,
            "change_30d": token.price_change_30d,
            "ath": fmt_price(token.ath),
            "ath_pct": token.ath_change_percentage,
        },
        "chart": {"dates": dates[-90:], "prices": prices[-90:]},
        "scores": {
            "final": round(final_score, 1),
            "verdict": verdict.value,
            "tokenomics": round(tok_result.score, 1),
            "qualitative": round(qual.score, 1),
            "technical": round(tech.score, 1),
            "risk": round(risk.overall_risk_score, 1),
        },
        "advanced_scores": {
            "composite": round(advanced.composite_score, 1),
            "conviction_tier": advanced.conviction_tier,
            "tokenomics_adv": round(td.weighted_score, 1),
            "qualitative_adv": round(qd.weighted_score, 1),
            "quantitative_adv": round(qm.weighted_score, 1),
            "dimensions": {
                "supply_mechanics": {"score": td.supply_mechanics, "detail": td.supply_detail},
                "distribution": {"score": td.distribution, "detail": td.distribution_detail},
                "utility": {"score": td.utility, "detail": td.utility_detail},
                "value_accrual": {"score": td.value_accrual, "detail": td.value_accrual_detail},
                "governance": {"score": td.governance, "detail": td.governance_detail},
                "vesting": {"score": td.vesting_unlocks, "detail": td.vesting_detail},
            },
            "qualitative_dims": {
                "team": {"score": round(qd.team, 1), "detail": qd.team_detail},
                "pmf": {"score": round(qd.product_market_fit, 1), "detail": qd.pmf_detail},
                "ecosystem": {"score": round(qd.ecosystem_partners, 1), "detail": qd.ecosystem_detail},
                "moat": {"score": round(qd.competitive_moat, 1), "detail": qd.moat_detail},
            },
            "velocity": {
                "estimated": round(advanced.velocity.estimated_velocity, 1),
                "risk": advanced.velocity.velocity_risk,
                "sinks": advanced.velocity.velocity_sinks,
                "detail": advanced.velocity.detail,
            },
            "real_yield": {
                "pct": round(advanced.real_yield.real_yield_pct, 1) if advanced.real_yield.real_yield_pct is not None else None,
                "is_real": advanced.real_yield.is_real_yield,
                "sustainability": advanced.real_yield.yield_sustainability,
                "detail": advanced.real_yield.detail,
            },
            "value_accrual": {
                "model": advanced.value_accrual.accrual_model,
                "mechanisms": advanced.value_accrual.mechanisms,
                "detail": advanced.value_accrual.detail,
            },
            "nvt": {"ratio": advanced.nvt_ratio, "signal": advanced.nvt_signal},
            "metcalfe": {"ratio": advanced.metcalfe_value_ratio, "signal": advanced.metcalfe_signal},
            "red_flags_auto": {
                "triggered": advanced.red_flags.triggered,
                "disqualified": advanced.red_flags.is_disqualified,
                "detail": advanced.red_flags.detail,
            },
        },
        "tokenomics": {
            "insider_pct": round(tok_result.distribution.insider_percentage, 1),
            "community_pct": round(tok_result.distribution.community_percentage, 1),
            "team_pct": round(tok_result.distribution.team_allocation, 1),
            "investor_pct": round(tok_result.distribution.investor_allocation, 1),
            "ecosystem_pct": round(tok_result.distribution.ecosystem_allocation, 1),
            "treasury_pct": round(tok_result.distribution.treasury_allocation, 1),
            "other_pct": round(tok_result.distribution.foundation_allocation + tok_result.distribution.airdrop_allocation, 1),
            "max_inflation": round(tok_result.inflation.max_inflation, 1),
            "supply_ratio": round(tok_result.inflation.supply_ratio * 100, 1),
            "fdv_mcap_ratio": round(tok_result.fdv_mcap_ratio, 1),
            "pu_ratio": round(tok_result.pu_ratio, 0) if tok_result.pu_ratio else None,
            "vesting_months": tok_result.vesting.vesting_duration_months,
            "cliff_months": tok_result.vesting.cliff_months,
            "utility": tok_result.utility.description,
            "has_real_demand": tok_result.utility.has_real_demand,
            "revenue_share": tok_result.utility.revenue_share,
        },
        "qualitative_detail": {
            "sentiment_score": round(sentiment.score, 1),
            "hype_index": round(sentiment.hype_index, 1),
            "organic_ratio": round(sentiment.organic_ratio * 100, 1),
            "overall_sentiment": round(sentiment.overall_sentiment, 2),
            "team_score": round(team.team_score, 1),
            "dev_activity": round(team.development_activity_score, 1),
            "commits_30d": team.github_commits_30d,
            "transparency": round(team.transparency_score, 1),
            "vc_score": round(vc.score, 1),
            "vc_reputation": round(vc.vc_reputation_score, 1),
            "tier1": vc.tier1_investors,
            "tier2": vc.tier2_investors,
            "cap_table_health": round(vc.cap_table_health, 1),
            "partnerships": vc.strategic_partners,
        },
        "technical_detail": {
            "trend": mom.trend.value,
            "rsi": round(mom.rsi, 1),
            "rsi_signal": mom.rsi_signal,
            "rsi_divergence": mom.rsi_divergence,
            "macd_histogram": round(mom.macd_histogram, 6),
            "macd_crossover": mom.macd_crossover,
            "bb_squeeze": mom.bb_squeeze,
            "bb_bandwidth": round(mom.bb_bandwidth * 100, 2),
            "golden_cross": mom.golden_cross,
            "death_cross": mom.death_cross,
            "price_vs_vwap": mom.price_vs_vwap,
            "vwap_vol_signal": mom.vwap_volume_signal,
            "volatility_30d": round(volat.historical_volatility_30d, 1),
            "regime": volat.market_regime.value,
            "atr_pct": round(volat.atr_percentage, 2),
            "choppiness": round(volat.choppiness_index, 1),
            "drawdown_30d": round(volat.max_drawdown_30d, 1),
            "drawdown_90d": round(volat.max_drawdown_90d, 1),
            "sharpe": round(volat.sharpe_ratio, 2) if volat.sharpe_ratio else None,
            "sortino": round(volat.sortino_ratio, 2) if volat.sortino_ratio else None,
            "confidence": round(volat.confidence_adjustment * 100, 0),
            "momentum_score": round(mom.score, 1),
            "volatility_score": round(volat.score, 1),
        },
        "risk_detail": {
            "red_flags": [{"category": f.category, "description": f.description} for f in risk.red_flags],
            "yellow_flags": [{"category": f.category, "description": f.description} for f in risk.yellow_flags],
            "green_flags": [{"category": f.category, "description": f.description} for f in risk.green_flags],
            "low_float_high_fdv": risk.low_float_high_fdv,
            "mercenary_incentives": risk.mercenary_incentives,
            "moral_hazard": round(risk.moral_hazard_risk, 0),
            "dumping_structure": risk.dumping_structure,
        },
    }


@app.route("/")
def index():
    return render_template("index.html", tokens=list(TOKENS.keys()))


def sanitize(obj):
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


@app.route("/api/analyze/<token_key>")
def analyze(token_key):
    if token_key not in TOKENS:
        return jsonify({"error": "Token not found"}), 404
    return jsonify(sanitize(run_analysis(token_key)))


@app.route("/api/memo/<token_key>")
def memo(token_key):
    """Generate complete investment memo for a token."""
    if token_key not in TOKENS:
        return jsonify({"error": "Token not found"}), 404

    base = _run_base_analysis(token_key)
    d = TOKENS[token_key]

    memo_gen = MemoGenerator()
    memo_data = memo_gen.generate(
        token=base["token"],
        community_data=d["community"],
        tokenomics=base["tok_result"],
        qualitative=base["qual"],
        technical=base["tech"],
        risk=base["risk"],
        advanced=base["advanced"],
        final_score=base["final_score"],
        verdict=base["verdict"],
    )
    return jsonify(sanitize(memo_data))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
