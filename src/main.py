"""
BSB Capital - Main Entry Point
Institutional-Grade Crypto Token Analysis Platform.

Usage:
    python -m src.main <token_name>
    python -m src.main ethereum
    python -m src.main bitcoin --no-technical
"""

import sys
import argparse
import logging
from datetime import datetime, timezone

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.core.data_fetcher import DataFetcher
from src.fundamental.tokenomics import TokenomicsAnalyzer
from src.qualitative.sentiment import SentimentAnalyzer
from src.qualitative.team_scoring import TeamScorer
from src.qualitative.vc_analysis import VCAnalyzer
from src.technical.indicators import TechnicalIndicatorEngine
from src.technical.volatility import VolatilityEngine
from src.technical.news_impact import NewsImpactAnalyzer
from src.risk.risk_engine import RiskEngine
from src.core.report_generator import ReportGenerator
from src.models.schemas import (
    AnalysisReport,
    QualitativeAnalysis,
    TechnicalAnalysis,
)

console = Console()
logger = logging.getLogger(__name__)


class CryptoAnalyzer:
    """
    Main orchestrator for the crypto analysis pipeline.

    Pipeline:
    1. Fetch token data from APIs
    2. Run fundamental tokenomics analysis
    3. Run qualitative analysis (sentiment, team, VCs)
    4. Run technical analysis (indicators, volatility, news)
    5. Run risk assessment
    6. Generate composite score and verdict
    7. Output formatted report
    """

    def __init__(self, api_key: str | None = None):
        self.fetcher = DataFetcher(coingecko_api_key=api_key)
        self.tokenomics_analyzer = TokenomicsAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.team_scorer = TeamScorer()
        self.vc_analyzer = VCAnalyzer()
        self.indicator_engine = TechnicalIndicatorEngine()
        self.volatility_engine = VolatilityEngine()
        self.news_analyzer = NewsImpactAnalyzer()
        self.risk_engine = RiskEngine()
        self.report_generator = ReportGenerator()

    def analyze(
        self,
        token_query: str,
        skip_technical: bool = False,
        known_founders: list[str] | None = None,
        known_investors: list[str] | None = None,
        known_partners: list[str] | None = None,
    ) -> AnalysisReport:
        """
        Run complete analysis pipeline for a token.

        Args:
            token_query: Token name or CoinGecko ID
            skip_technical: Skip technical analysis (faster)
            known_founders: Optional list of known founder names
            known_investors: Optional list of known investor names
            known_partners: Optional list of known strategic partners
        """
        report = AnalysisReport()
        report.analysis_timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            # Step 1: Fetch token data
            task = progress.add_task("Buscando token...", total=None)
            token_id = self.fetcher.search_token(token_query)
            if not token_id:
                console.print(
                    f"[red]Error: No se encontro el token '{token_query}'[/red]"
                )
                sys.exit(1)

            progress.update(task, description="Obteniendo datos de mercado...")
            token_data = self.fetcher.get_token_data(token_id)
            if not token_data:
                console.print("[red]Error: No se pudieron obtener datos del token[/red]")
                sys.exit(1)
            report.token = token_data
            progress.update(task, description=f"Token encontrado: {token_data.name} ({token_data.symbol})")

            # Step 2: Fetch community/developer data
            progress.update(task, description="Obteniendo datos de comunidad...")
            community_data = self.fetcher.get_community_data(token_id)

            # Step 3: Fundamental Analysis
            progress.update(task, description="Analizando tokenomics...")
            report.tokenomics = self.tokenomics_analyzer.analyze(
                token_data, community_data
            )

            # Step 4: Qualitative Analysis
            progress.update(task, description="Analizando sentimiento de mercado...")
            volume_ratio = 1.0
            if token_data.volume_24h > 0 and token_data.market_cap > 0:
                volume_ratio = token_data.volume_24h / (token_data.market_cap * 0.01)
            sentiment = self.sentiment_analyzer.analyze(
                community_data,
                token_data.name,
                price_change_7d=token_data.price_change_7d,
                volume_change_ratio=min(5.0, volume_ratio),
            )

            progress.update(task, description="Evaluando equipo de desarrollo...")
            team = self.team_scorer.analyze(
                community_data,
                known_founders=known_founders,
            )

            progress.update(task, description="Analizando inversores y partnerships...")
            vc = self.vc_analyzer.analyze(
                token_data.name,
                known_investors=known_investors,
                known_partners=known_partners,
            )

            report.qualitative = QualitativeAnalysis(
                sentiment=sentiment,
                team=team,
                vc=vc,
                score=(sentiment.score * 0.35 + team.team_score * 0.35 + vc.score * 0.30),
            )

            # Step 5: Technical Analysis
            if not skip_technical:
                progress.update(task, description="Obteniendo datos OHLCV...")
                ohlcv = self.fetcher.get_ohlcv(token_id, days=365)

                if ohlcv is not None and len(ohlcv) > 30:
                    progress.update(task, description="Calculando indicadores tecnicos...")
                    momentum = self.indicator_engine.analyze(ohlcv)

                    progress.update(task, description="Analizando volatilidad y regimenes...")
                    volatility = self.volatility_engine.analyze(ohlcv)

                    progress.update(task, description="Evaluando impacto de noticias...")
                    news = self.news_analyzer.analyze(
                        token_data.name,
                        description=community_data.get("description", ""),
                        has_upcoming_unlocks=(
                            report.tokenomics.inflation.max_inflation > 30
                        ),
                        inflation_rate=report.tokenomics.inflation.max_inflation,
                    )

                    report.technical = TechnicalAnalysis(
                        momentum=momentum,
                        volatility=volatility,
                        news_impact=news,
                        score=(
                            momentum.score * 0.45
                            + volatility.score * 0.35
                            + news.score * 0.20
                        ),
                    )
                else:
                    progress.update(
                        task,
                        description="[yellow]Datos OHLCV insuficientes, omitiendo AT[/yellow]",
                    )
            else:
                progress.update(task, description="Analisis tecnico omitido (--no-technical)")

            # Step 6: Risk Assessment
            progress.update(task, description="Evaluando riesgos...")
            report.risk = self.risk_engine.assess(
                report.tokenomics, report.qualitative, report.technical
            )

            # Step 7: Final Score & Verdict
            progress.update(task, description="Calculando veredicto final...")
            report.final_score, report.verdict = self.risk_engine.compute_verdict(
                report.tokenomics,
                report.qualitative,
                report.technical,
                report.risk,
            )

            progress.update(task, description="Analisis completado.")

        return report

    def print_report(self, report: AnalysisReport) -> None:
        """Print formatted report."""
        self.report_generator.generate(report)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="BSB Capital - Crypto Token Analysis Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python -m src.main ethereum
  python -m src.main solana --founders "Anatoly Yakovenko"
  python -m src.main uniswap --investors "a16z,Paradigm" --partners "Coinbase"
  python -m src.main bitcoin --no-technical
        """,
    )
    parser.add_argument("token", help="Nombre del token a analizar")
    parser.add_argument(
        "--no-technical",
        action="store_true",
        help="Omitir analisis tecnico (mas rapido)",
    )
    parser.add_argument(
        "--founders",
        type=str,
        default=None,
        help="Nombres de fundadores conocidos (separados por coma)",
    )
    parser.add_argument(
        "--investors",
        type=str,
        default=None,
        help="Nombres de inversores conocidos (separados por coma)",
    )
    parser.add_argument(
        "--partners",
        type=str,
        default=None,
        help="Nombres de partners estrategicos (separados por coma)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="CoinGecko API key (opcional, para limites mas altos)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar logs detallados",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Parse comma-separated lists
    founders = args.founders.split(",") if args.founders else None
    investors = args.investors.split(",") if args.investors else None
    partners = args.partners.split(",") if args.partners else None

    # Run analysis
    analyzer = CryptoAnalyzer(api_key=args.api_key)

    console.print(Panel(
        "[bold cyan]BSB CAPITAL[/bold cyan]\n"
        "[dim]Plataforma de Analisis de Criptoactivos - Nivel Institucional[/dim]\n"
        f"\nAnalizando: [bold]{args.token}[/bold]",
        border_style="cyan",
    ))

    report = analyzer.analyze(
        args.token,
        skip_technical=args.no_technical,
        known_founders=founders,
        known_investors=investors,
        known_partners=partners,
    )

    analyzer.print_report(report)


if __name__ == "__main__":
    main()
