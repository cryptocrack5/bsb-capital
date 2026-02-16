"""
BSB Capital - Example: Programmatic Token Analysis

Shows how to use the platform programmatically with custom data overrides.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import CryptoAnalyzer
from src.models.schemas import DistributionData, VestingSchedule


def analyze_with_known_data():
    """
    Example: Analyze Ethereum with known tokenomics data.
    Shows how to override estimated data with real values.
    """
    analyzer = CryptoAnalyzer()

    # Run analysis with known metadata
    report = analyzer.analyze(
        "ethereum",
        known_founders=["Vitalik Buterin"],
        known_investors=["Paradigm", "a16z", "Polychain Capital"],
        known_partners=["Microsoft", "JPMorgan"],
    )

    analyzer.print_report(report)
    return report


def analyze_with_custom_tokenomics():
    """
    Example: Analyze a token with manually provided tokenomics data.
    Useful when you have data from docs/whitepapers.
    """
    analyzer = CryptoAnalyzer()

    # Custom distribution data (from whitepaper)
    custom_distribution = DistributionData(
        team_allocation=15.0,
        investor_allocation=17.0,
        community_allocation=40.0,
        ecosystem_allocation=18.0,
        treasury_allocation=10.0,
        insider_percentage=32.0,
        community_percentage=58.0,
        data_available=True,
    )

    # Custom vesting data
    custom_vesting = VestingSchedule(
        cliff_months=12,
        vesting_duration_months=48,
        tge_unlock_percentage=10.0,
        monthly_unlock_rate=1.875,
        has_burn_mechanism=True,
        has_buyback_mechanism=False,
        data_available=True,
    )

    # The tokenomics analyzer accepts overrides
    from src.core.data_fetcher import DataFetcher
    from src.fundamental.tokenomics import TokenomicsAnalyzer

    fetcher = DataFetcher()
    token_id = fetcher.search_token("solana")
    token_data = fetcher.get_token_data(token_id)
    community_data = fetcher.get_community_data(token_id)

    tokenomics_analyzer = TokenomicsAnalyzer()
    tokenomics = tokenomics_analyzer.analyze(
        token_data,
        community_data,
        distribution_override=custom_distribution,
        vesting_override=custom_vesting,
    )

    print(f"\nTokenomics Score: {tokenomics.score:.0f}/100")
    print(f"Distribution: {tokenomics.distribution.insider_percentage:.0f}% insiders")
    print(f"Inflation Max: {tokenomics.inflation.max_inflation:.1f}%")
    print(f"FDV/MCap: {tokenomics.fdv_mcap_ratio:.1f}x")


def quick_analysis():
    """
    Example: Quick analysis with just a token name.
    Uses all estimated/public data.
    """
    analyzer = CryptoAnalyzer()
    report = analyzer.analyze("bitcoin")
    analyzer.print_report(report)


if __name__ == "__main__":
    print("=" * 60)
    print("BSB Capital - Example Analysis")
    print("=" * 60)

    if len(sys.argv) > 1:
        token = sys.argv[1]
        analyzer = CryptoAnalyzer()
        report = analyzer.analyze(token)
        analyzer.print_report(report)
    else:
        print("\nEjecutando analisis de Ethereum con datos conocidos...\n")
        analyze_with_known_data()
