"""
BSB Capital - Demo Mode
Generates a full analysis report using sample data for preview purposes.
Use this when API access is unavailable.

Usage:
    python -m examples.demo_preview
    python -m examples.demo_preview --token ethereum
"""

import sys
import os
import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.schemas import (
    TokenMarketData, TokenType, AnalysisReport,
    QualitativeAnalysis, TechnicalAnalysis,
    DistributionData, VestingSchedule,
)
from src.fundamental.tokenomics import TokenomicsAnalyzer
from src.qualitative.sentiment import SentimentAnalyzer
from src.qualitative.team_scoring import TeamScorer
from src.qualitative.vc_analysis import VCAnalyzer
from src.technical.indicators import TechnicalIndicatorEngine
from src.technical.volatility import VolatilityEngine
from src.technical.news_impact import NewsImpactAnalyzer
from src.risk.risk_engine import RiskEngine
from src.core.report_generator import ReportGenerator


# ============================================================================
# SAMPLE TOKEN DATA
# ============================================================================

SAMPLE_TOKENS = {
    "bitcoin": TokenMarketData(
        name="Bitcoin",
        symbol="BTC",
        token_type=TokenType.L1,
        price_usd=97_432.15,
        market_cap=1_932_000_000_000,
        fully_diluted_valuation=2_046_000_000_000,
        circulating_supply=19_820_000,
        total_supply=21_000_000,
        max_supply=21_000_000,
        volume_24h=28_500_000_000,
        price_change_24h=1.24,
        price_change_7d=4.87,
        price_change_30d=-2.15,
        ath=109_114.88,
        ath_change_percentage=-10.7,
        atl=67.81,
        coingecko_id="bitcoin",
    ),
    "ethereum": TokenMarketData(
        name="Ethereum",
        symbol="ETH",
        token_type=TokenType.L1,
        price_usd=2_684.32,
        market_cap=323_500_000_000,
        fully_diluted_valuation=323_500_000_000,
        circulating_supply=120_520_000,
        total_supply=120_520_000,
        max_supply=None,
        volume_24h=14_200_000_000,
        price_change_24h=-0.83,
        price_change_7d=2.14,
        price_change_30d=-8.42,
        ath=4_878.26,
        ath_change_percentage=-44.97,
        atl=0.432979,
        coingecko_id="ethereum",
    ),
    "solana": TokenMarketData(
        name="Solana",
        symbol="SOL",
        token_type=TokenType.L1,
        price_usd=193.47,
        market_cap=94_200_000_000,
        fully_diluted_valuation=113_800_000_000,
        circulating_supply=486_900_000,
        total_supply=588_200_000,
        max_supply=None,
        volume_24h=3_100_000_000,
        price_change_24h=2.31,
        price_change_7d=8.67,
        price_change_30d=-12.53,
        ath=293.31,
        ath_change_percentage=-34.03,
        atl=0.50052,
        coingecko_id="solana",
    ),
    "arbitrum": TokenMarketData(
        name="Arbitrum",
        symbol="ARB",
        token_type=TokenType.L2,
        price_usd=0.3821,
        market_cap=1_530_000_000,
        fully_diluted_valuation=3_820_000_000,
        circulating_supply=4_006_000_000,
        total_supply=10_000_000_000,
        max_supply=10_000_000_000,
        volume_24h=285_000_000,
        price_change_24h=-1.45,
        price_change_7d=-5.23,
        price_change_30d=-18.67,
        ath=2.39,
        ath_change_percentage=-84.01,
        atl=0.3445,
        coingecko_id="arbitrum",
    ),
}

SAMPLE_COMMUNITY = {
    "bitcoin": {
        "description": "Bitcoin is a decentralized digital currency with no central bank or single administrator. It uses peer-to-peer technology for instant payments. Bitcoin is the first cryptocurrency, using proof-of-work consensus and serving as a store of value and payment system.",
        "categories": ["Cryptocurrency", "Layer 1", "Store of Value", "Proof of Work"],
        "community": {
            "twitter_followers": 6_800_000,
            "reddit_subscribers": 5_200_000,
            "reddit_accounts_active_48h": 12_500,
            "telegram_channel_user_count": 120_000,
        },
        "developer": {
            "commit_count_4_weeks": 180,
            "code_additions_deletions_4_weeks": {"additions": 4500, "deletions": 2100},
        },
        "links": {
            "homepage": ["https://bitcoin.org"],
            "twitter_screen_name": "bitcoin",
            "subreddit_url": "https://reddit.com/r/bitcoin",
            "repos_url": {"github": ["https://github.com/bitcoin/bitcoin"]},
        },
    },
    "ethereum": {
        "description": "Ethereum is a decentralized platform for smart contracts and dApps. It uses proof-of-stake consensus with real yield from staking (validator rewards from transaction fees). It features governance, gas token functionality, and EIP-1559 burn mechanism with revenue sharing through staking.",
        "categories": ["Smart Contract Platform", "Layer 1", "DeFi Ecosystem"],
        "community": {
            "twitter_followers": 3_400_000,
            "reddit_subscribers": 2_800_000,
            "reddit_accounts_active_48h": 8_200,
            "telegram_channel_user_count": 85_000,
        },
        "developer": {
            "commit_count_4_weeks": 320,
            "code_additions_deletions_4_weeks": {"additions": 12000, "deletions": 5500},
        },
        "links": {
            "homepage": ["https://ethereum.org"],
            "twitter_screen_name": "ethereum",
            "subreddit_url": "https://reddit.com/r/ethereum",
            "repos_url": {"github": ["https://github.com/ethereum/go-ethereum"]},
        },
    },
    "solana": {
        "description": "Solana is a high-performance Layer 1 blockchain supporting smart contracts and DeFi. It uses proof-of-stake and proof-of-history consensus. SOL is the gas token used for transaction fees and staking with validator rewards.",
        "categories": ["Smart Contract Platform", "Layer 1", "DeFi"],
        "community": {
            "twitter_followers": 2_900_000,
            "reddit_subscribers": 320_000,
            "reddit_accounts_active_48h": 3_800,
            "telegram_channel_user_count": 45_000,
        },
        "developer": {
            "commit_count_4_weeks": 250,
            "code_additions_deletions_4_weeks": {"additions": 8500, "deletions": 3200},
        },
        "links": {
            "homepage": ["https://solana.com"],
            "twitter_screen_name": "solana",
            "subreddit_url": "https://reddit.com/r/solana",
            "repos_url": {"github": ["https://github.com/solana-labs/solana"]},
        },
    },
    "arbitrum": {
        "description": "Arbitrum is a Layer 2 scaling solution for Ethereum using optimistic rollups. ARB is the governance token used for DAO voting. The protocol generates fees from transaction processing but does not currently share revenue with token holders.",
        "categories": ["Layer 2", "Scaling", "Optimistic Rollup"],
        "community": {
            "twitter_followers": 980_000,
            "reddit_subscribers": 85_000,
            "reddit_accounts_active_48h": 1_200,
            "telegram_channel_user_count": 32_000,
        },
        "developer": {
            "commit_count_4_weeks": 145,
            "code_additions_deletions_4_weeks": {"additions": 5200, "deletions": 2800},
        },
        "links": {
            "homepage": ["https://arbitrum.io"],
            "twitter_screen_name": "arbitrum",
            "subreddit_url": "https://reddit.com/r/arbitrum",
            "repos_url": {"github": ["https://github.com/OffchainLabs/nitro"]},
        },
    },
}

SAMPLE_METADATA = {
    "bitcoin": {
        "founders": ["Satoshi Nakamoto"],
        "investors": [],
        "partners": ["Lightning Network", "MicroStrategy", "BlackRock"],
        "distribution": DistributionData(
            team_allocation=0.0,
            investor_allocation=0.0,
            community_allocation=100.0,
            ecosystem_allocation=0.0,
            insider_percentage=0.0,
            community_percentage=100.0,
            data_available=True,
        ),
    },
    "ethereum": {
        "founders": ["Vitalik Buterin"],
        "investors": ["Paradigm", "a16z", "Polychain Capital"],
        "partners": ["Microsoft", "JPMorgan", "Visa", "BlackRock"],
        "distribution": DistributionData(
            team_allocation=9.9,
            investor_allocation=16.5,
            community_allocation=50.0,
            ecosystem_allocation=13.6,
            foundation_allocation=5.0,
            treasury_allocation=5.0,
            insider_percentage=26.4,
            community_percentage=63.6,
            top_10_wallet_concentration=35.2,
            data_available=True,
        ),
    },
    "solana": {
        "founders": ["Anatoly Yakovenko"],
        "investors": ["a16z", "Polychain Capital", "Multicoin Capital", "Jump Crypto"],
        "partners": ["Google Cloud", "Visa"],
        "distribution": DistributionData(
            team_allocation=12.8,
            investor_allocation=24.2,
            community_allocation=38.9,
            ecosystem_allocation=14.1,
            foundation_allocation=10.0,
            insider_percentage=37.0,
            community_percentage=53.0,
            data_available=True,
        ),
    },
    "arbitrum": {
        "founders": [],
        "investors": ["Pantera Capital", "Lightspeed", "Polychain Capital"],
        "partners": [],
        "distribution": DistributionData(
            team_allocation=26.9,
            investor_allocation=17.5,
            community_allocation=11.6,
            ecosystem_allocation=1.1,
            treasury_allocation=42.8,
            airdrop_allocation=11.6,
            insider_percentage=44.4,
            community_percentage=24.3,
            data_available=True,
        ),
    },
}


def generate_sample_ohlcv(token_key: str, days: int = 300) -> pd.DataFrame:
    """Generate realistic OHLCV data for demo."""
    np.random.seed(hash(token_key) % 2**31)
    token = SAMPLE_TOKENS[token_key]

    # Start from a historical price and trend toward current
    start_price = token.price_usd * np.random.uniform(0.6, 1.4)
    end_price = token.price_usd

    # Generate trending random walk
    trend = np.linspace(0, np.log(end_price / start_price), days)
    noise = np.cumsum(np.random.randn(days) * 0.025)
    log_prices = np.log(start_price) + trend + noise
    close_prices = np.exp(log_prices)

    # Generate OHLCV
    volatility = np.abs(np.random.randn(days)) * close_prices * 0.02
    high_prices = close_prices + volatility
    low_prices = close_prices - volatility
    open_prices = close_prices + np.random.randn(days) * close_prices * 0.005

    base_volume = token.volume_24h
    volumes = base_volume * np.exp(np.random.randn(days) * 0.5)

    df = pd.DataFrame({
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volumes,
    }, index=pd.date_range(end=datetime.now(), periods=days, freq="D"))

    return df


def run_demo(token_key: str):
    """Run full demo analysis with sample data."""
    if token_key not in SAMPLE_TOKENS:
        print(f"Token demo disponibles: {', '.join(SAMPLE_TOKENS.keys())}")
        return

    token = SAMPLE_TOKENS[token_key]
    community_data = SAMPLE_COMMUNITY[token_key]
    meta = SAMPLE_METADATA[token_key]

    report = AnalysisReport()
    report.token = token
    report.analysis_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Fundamental
    tokenomics_analyzer = TokenomicsAnalyzer()
    report.tokenomics = tokenomics_analyzer.analyze(
        token, community_data,
        distribution_override=meta.get("distribution"),
    )

    # Qualitative - Sentiment
    sentiment_analyzer = SentimentAnalyzer()
    volume_ratio = token.volume_24h / (token.market_cap * 0.01) if token.market_cap > 0 else 1.0
    sentiment = sentiment_analyzer.analyze(
        community_data, token.name,
        price_change_7d=token.price_change_7d,
        volume_change_ratio=min(5.0, volume_ratio),
    )

    # Qualitative - Team
    team_scorer = TeamScorer()
    team = team_scorer.analyze(
        community_data,
        known_founders=meta.get("founders"),
    )

    # Qualitative - VCs
    vc_analyzer = VCAnalyzer()
    vc = vc_analyzer.analyze(
        token.name,
        known_investors=meta.get("investors"),
        known_partners=meta.get("partners"),
    )

    report.qualitative = QualitativeAnalysis(
        sentiment=sentiment,
        team=team,
        vc=vc,
        score=(sentiment.score * 0.35 + team.team_score * 0.35 + vc.score * 0.30),
    )

    # Technical
    ohlcv = generate_sample_ohlcv(token_key)
    indicator_engine = TechnicalIndicatorEngine()
    momentum = indicator_engine.analyze(ohlcv)

    volatility_engine = VolatilityEngine()
    volatility = volatility_engine.analyze(ohlcv)

    news_analyzer = NewsImpactAnalyzer()
    news = news_analyzer.analyze(
        token.name,
        description=community_data.get("description", ""),
        has_upcoming_unlocks=(report.tokenomics.inflation.max_inflation > 30),
        inflation_rate=report.tokenomics.inflation.max_inflation,
    )

    report.technical = TechnicalAnalysis(
        momentum=momentum,
        volatility=volatility,
        news_impact=news,
        score=(momentum.score * 0.45 + volatility.score * 0.35 + news.score * 0.20),
    )

    # Risk
    risk_engine = RiskEngine()
    report.risk = risk_engine.assess(
        report.tokenomics, report.qualitative, report.technical,
    )

    report.final_score, report.verdict = risk_engine.compute_verdict(
        report.tokenomics, report.qualitative, report.technical, report.risk,
    )

    # Print report
    generator = ReportGenerator()
    generator.generate(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BSB Capital Demo Preview")
    parser.add_argument(
        "--token", "-t", default="ethereum",
        choices=list(SAMPLE_TOKENS.keys()),
        help="Token to analyze (default: ethereum)",
    )
    args = parser.parse_args()
    run_demo(args.token)
