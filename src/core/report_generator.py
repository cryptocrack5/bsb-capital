"""
BSB Capital - Report Generator
Produces rich, formatted analysis reports.
"""

import logging
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

from src.models.schemas import (
    AnalysisReport,
    RiskSignal,
    Verdict,
    VolatilityRegime,
    TrendDirection,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates formatted reports for terminal output."""

    def __init__(self):
        self.console = Console()

    def generate(self, report: AnalysisReport) -> None:
        """Generate and print the complete analysis report."""
        self.console.print()
        self._print_header(report)
        self._print_executive_summary(report)
        self._print_market_data(report)
        self._print_tokenomics(report)
        self._print_qualitative(report)
        self._print_technical(report)
        self._print_risk_assessment(report)
        self._print_final_verdict(report)
        self._print_disclaimer(report)
        self.console.print()

    def _print_header(self, report: AnalysisReport) -> None:
        """Print report header."""
        title = Text()
        title.append("BSB CAPITAL", style="bold cyan")
        title.append(" | ", style="dim")
        title.append("Crypto Analysis Platform", style="italic")

        subtitle = Text()
        subtitle.append(f"\n{report.token.name} ({report.token.symbol})", style="bold white")
        subtitle.append(f"\nTipo: {report.token.token_type.value}", style="dim")
        subtitle.append(f"\nFecha: {report.analysis_timestamp}", style="dim")

        self.console.print(Panel(
            title + subtitle,
            border_style="cyan",
            box=box.DOUBLE,
            padding=(1, 2),
        ))

    def _print_executive_summary(self, report: AnalysisReport) -> None:
        """Print executive summary with verdict."""
        verdict_colors = {
            Verdict.STRONG_BUY: "bold green",
            Verdict.BUY: "green",
            Verdict.NEUTRAL: "yellow",
            Verdict.SELL: "red",
            Verdict.STRONG_SELL: "bold red",
        }
        color = verdict_colors.get(report.verdict, "white")

        summary = Text()
        summary.append("VEREDICTO: ", style="bold")
        summary.append(f"{report.verdict.value}", style=color)
        summary.append(f" (Score: {report.final_score:.1f}/100)\n\n", style="dim")

        # Pros
        green_flags = report.risk.green_flags
        if green_flags:
            summary.append("PROS:\n", style="bold green")
            for flag in green_flags[:5]:
                summary.append(f"  + {flag.description}\n", style="green")
            summary.append("\n")

        # Red Flags
        red_flags = report.risk.red_flags
        if red_flags:
            summary.append("RED FLAGS:\n", style="bold red")
            for flag in red_flags[:5]:
                summary.append(f"  ! {flag.description}\n", style="red")

        self.console.print(Panel(
            summary,
            title="[bold]RESUMEN EJECUTIVO[/bold]",
            border_style="white",
            box=box.ROUNDED,
        ))

    def _print_market_data(self, report: AnalysisReport) -> None:
        """Print market data table."""
        t = report.token
        table = Table(
            title="Datos de Mercado",
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Metrica", style="bold")
        table.add_column("Valor", justify="right")
        table.add_column("Metrica", style="bold")
        table.add_column("Valor", justify="right")

        table.add_row(
            "Precio", f"${t.price_usd:,.6f}" if t.price_usd < 1 else f"${t.price_usd:,.2f}",
            "Market Cap", f"${t.market_cap:,.0f}",
        )
        table.add_row(
            "FDV", f"${t.fully_diluted_valuation:,.0f}",
            "Vol 24h", f"${t.volume_24h:,.0f}",
        )
        table.add_row(
            "Circ. Supply", f"{t.circulating_supply:,.0f}",
            "Total Supply", f"{t.total_supply:,.0f}",
        )

        chg_24h_style = "green" if t.price_change_24h >= 0 else "red"
        chg_7d_style = "green" if t.price_change_7d >= 0 else "red"
        chg_30d_style = "green" if t.price_change_30d >= 0 else "red"

        table.add_row(
            "Cambio 24h", Text(f"{t.price_change_24h:+.2f}%", style=chg_24h_style),
            "Cambio 7d", Text(f"{t.price_change_7d:+.2f}%", style=chg_7d_style),
        )
        table.add_row(
            "Cambio 30d", Text(f"{t.price_change_30d:+.2f}%", style=chg_30d_style),
            "ATH", f"${t.ath:,.2f} ({t.ath_change_percentage:+.1f}%)",
        )

        self.console.print(table)

    def _print_tokenomics(self, report: AnalysisReport) -> None:
        """Print tokenomics analysis."""
        tok = report.tokenomics

        table = Table(
            title="Analisis de Tokenomics",
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Factor", style="bold")
        table.add_column("Valor")
        table.add_column("Evaluacion")

        # Distribution
        insider_style = (
            "red" if tok.distribution.insider_percentage > 50
            else "yellow" if tok.distribution.insider_percentage > 30
            else "green"
        )
        table.add_row(
            "Insiders",
            f"{tok.distribution.insider_percentage:.1f}%",
            Text(
                "ALTO RIESGO" if tok.distribution.insider_percentage > 50
                else "MODERADO" if tok.distribution.insider_percentage > 30
                else "FAVORABLE",
                style=insider_style,
            ),
        )
        table.add_row(
            "Comunidad",
            f"{tok.distribution.community_percentage:.1f}%",
            "",
        )

        # Inflation
        inf_style = (
            "red" if tok.inflation.max_inflation > 100
            else "yellow" if tok.inflation.max_inflation > 50
            else "green"
        )
        table.add_row(
            "Inflacion Max",
            f"{tok.inflation.max_inflation:.1f}%",
            Text(
                "PELIGROSO" if tok.inflation.max_inflation > 100
                else "MODERADO" if tok.inflation.max_inflation > 50
                else "CONTROLADO",
                style=inf_style,
            ),
        )
        table.add_row(
            "Supply Ratio",
            f"{tok.inflation.supply_ratio:.1%}",
            f"(Circulante/Total)",
        )

        # FDV
        fdv_style = (
            "red" if tok.fdv_mcap_ratio > 10
            else "yellow" if tok.fdv_mcap_ratio > 5
            else "green"
        )
        table.add_row(
            "FDV/MCap",
            f"{tok.fdv_mcap_ratio:.1f}x",
            Text(
                "LOW FLOAT/HIGH FDV" if tok.fdv_mcap_ratio > 10
                else "MODERADO" if tok.fdv_mcap_ratio > 5
                else "SALUDABLE",
                style=fdv_style,
            ),
        )

        # Vesting
        table.add_row(
            "Vesting Est.",
            f"{tok.vesting.vesting_duration_months} meses",
            f"Cliff: {tok.vesting.cliff_months} meses",
        )

        # PU Ratio
        if tok.pu_ratio is not None:
            pu_style = (
                "red" if tok.pu_ratio > 100
                else "yellow" if tok.pu_ratio > 60
                else "green"
            )
            table.add_row(
                "PU Ratio",
                f"{tok.pu_ratio:.0f}",
                Text(
                    "SOBREVALUADO" if tok.pu_ratio > 100
                    else "JUSTO" if tok.pu_ratio > 60
                    else "INFRAVALUADO",
                    style=pu_style,
                ),
            )

        # Utility
        table.add_row(
            "Utilidad",
            tok.utility.description,
            Text(
                "DEMANDA REAL" if tok.utility.has_real_demand else "SIN DEMANDA REAL",
                style="green" if tok.utility.has_real_demand else "red",
            ),
        )

        # Score
        score_style = "green" if tok.score >= 65 else "yellow" if tok.score >= 45 else "red"
        table.add_row(
            "Score Tokenomics",
            Text(f"{tok.score:.0f}/100", style=score_style),
            "",
        )

        if not tok.distribution.data_available:
            table.add_row(
                "",
                Text("[Datos estimados - no confirmados]", style="dim italic"),
                "",
            )

        self.console.print(table)

    def _print_qualitative(self, report: AnalysisReport) -> None:
        """Print qualitative analysis."""
        qual = report.qualitative

        table = Table(
            title="Analisis Cualitativo",
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("Dimension", style="bold")
        table.add_column("Score", justify="center")
        table.add_column("Detalle")

        # Sentiment
        sent = qual.sentiment
        sent_style = "green" if sent.score >= 65 else "yellow" if sent.score >= 45 else "red"
        table.add_row(
            "Sentimiento",
            Text(f"{sent.score:.0f}/100", style=sent_style),
            f"Hype: {sent.hype_index:.0f} | Organico: {sent.organic_ratio:.0%} | Sent: {sent.overall_sentiment:+.2f}",
        )

        # Team
        team = qual.team
        team_style = "green" if team.team_score >= 65 else "yellow" if team.team_score >= 45 else "red"
        dev_info = f"Commits 30d: {team.github_commits_30d} | Dev Score: {team.development_activity_score:.0f}"
        table.add_row(
            "Equipo",
            Text(f"{team.team_score:.0f}/100", style=team_style),
            dev_info,
        )

        # VCs
        vc = qual.vc
        vc_style = "green" if vc.score >= 65 else "yellow" if vc.score >= 45 else "red"
        t1 = f"Tier-1: {len(vc.tier1_investors)}" if vc.tier1_investors else "Sin Tier-1"
        table.add_row(
            "Inversores/VCs",
            Text(f"{vc.score:.0f}/100", style=vc_style),
            f"{t1} | Cap Table: {vc.cap_table_health:.0f}/100",
        )

        # Overall
        overall_style = "green" if qual.score >= 65 else "yellow" if qual.score >= 45 else "red"
        table.add_row(
            "Score Total",
            Text(f"{qual.score:.0f}/100", style=overall_style),
            "",
        )

        self.console.print(table)

    def _print_technical(self, report: AnalysisReport) -> None:
        """Print technical analysis."""
        tech = report.technical

        table = Table(
            title="Analisis Tecnico",
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold yellow",
        )
        table.add_column("Indicador", style="bold")
        table.add_column("Valor", justify="right")
        table.add_column("Senal")

        mom = tech.momentum
        vol = tech.volatility

        # Trend
        trend_colors = {
            TrendDirection.BULLISH: "green",
            TrendDirection.BEARISH: "red",
            TrendDirection.SIDEWAYS: "yellow",
        }
        table.add_row(
            "Tendencia",
            mom.trend.value,
            Text(mom.trend.value, style=trend_colors.get(mom.trend, "white")),
        )

        # RSI
        rsi_style = "red" if mom.rsi_signal == "overbought" else "green" if mom.rsi_signal == "oversold" else "white"
        rsi_extra = f" [{mom.rsi_divergence} div]" if mom.rsi_divergence else ""
        table.add_row(
            "RSI(14)",
            f"{mom.rsi:.1f}",
            Text(f"{mom.rsi_signal}{rsi_extra}", style=rsi_style),
        )

        # MACD
        macd_style = "green" if mom.macd_histogram > 0 else "red"
        macd_cross = f" | {mom.macd_crossover} cross" if mom.macd_crossover else ""
        table.add_row(
            "MACD",
            f"{mom.macd_value:.6f}",
            Text(f"Hist: {mom.macd_histogram:+.6f}{macd_cross}", style=macd_style),
        )

        # MAs
        table.add_row(
            "MAs",
            f"20: {mom.ma_20:.4f}",
            f"50: {mom.ma_50:.4f} | 200: {mom.ma_200:.4f}",
        )

        if mom.golden_cross:
            table.add_row("", "", Text("GOLDEN CROSS", style="bold green"))
        elif mom.death_cross:
            table.add_row("", "", Text("DEATH CROSS", style="bold red"))

        # Bollinger
        bb_info = "SQUEEZE" if mom.bb_squeeze else f"BW: {mom.bb_bandwidth:.2%}"
        table.add_row(
            "Bollinger",
            f"Mid: {mom.bb_middle:.4f}",
            Text(bb_info, style="yellow" if mom.bb_squeeze else "white"),
        )

        # VWAP
        if mom.vwap > 0:
            vwap_style = "green" if mom.price_vs_vwap == "above" else "red"
            vol_signal = " + VOL CONFIRM" if mom.vwap_volume_signal else ""
            table.add_row(
                "VWAP",
                f"{mom.vwap:.4f}",
                Text(f"Precio {mom.price_vs_vwap}{vol_signal}", style=vwap_style),
            )

        # Volatility
        vol_colors = {
            VolatilityRegime.LOW: "green",
            VolatilityRegime.NORMAL: "white",
            VolatilityRegime.HIGH: "yellow",
            VolatilityRegime.EXTREME: "red",
        }
        table.add_row(
            "Volatilidad",
            f"HV30: {vol.historical_volatility_30d:.1f}%",
            Text(vol.market_regime.value, style=vol_colors.get(vol.market_regime, "white")),
        )
        table.add_row(
            "ATR",
            f"{vol.atr:.6f} ({vol.atr_percentage:.2f}%)",
            f"Stop: {vol.dynamic_stop_loss:.6f}",
        )
        table.add_row(
            "Choppiness",
            f"{vol.choppiness_index:.1f}",
            Text(
                "TRENDING" if vol.choppiness_index < 38.2
                else "RANGING" if vol.choppiness_index > 61.8
                else "TRANSICION",
                style="green" if vol.choppiness_index < 38.2 else "yellow",
            ),
        )
        table.add_row(
            "Max Drawdown",
            f"30d: {vol.max_drawdown_30d:.1f}%",
            f"90d: {vol.max_drawdown_90d:.1f}%",
        )

        if vol.sharpe_ratio is not None:
            table.add_row(
                "Sharpe/Sortino",
                f"{vol.sharpe_ratio:.2f}",
                f"Sortino: {vol.sortino_ratio:.2f}" if vol.sortino_ratio else "",
            )

        table.add_row(
            "Confianza",
            f"{vol.confidence_adjustment:.0%}",
            Text(
                "ALTA" if vol.confidence_adjustment > 0.7
                else "MEDIA" if vol.confidence_adjustment > 0.4
                else "BAJA - PRECAUCION",
                style="green" if vol.confidence_adjustment > 0.7
                else "yellow" if vol.confidence_adjustment > 0.4
                else "red",
            ),
        )

        # News Impact
        news = tech.news_impact
        if news.significant_events:
            table.add_row("", "", "")
            table.add_row(
                "Eventos",
                f"Sent: {news.recent_news_sentiment:+.2f}",
                f"Reg Risk: {news.regulatory_risk:.0f}/100 | BTRSTN: {news.buy_rumor_sell_news_risk:.0f}/100",
            )

        # Scores
        table.add_row("", "", "")
        mom_style = "green" if mom.score >= 60 else "yellow" if mom.score >= 40 else "red"
        vol_s_style = "green" if vol.score >= 60 else "yellow" if vol.score >= 40 else "red"
        table.add_row(
            "Score Momentum",
            Text(f"{mom.score:.0f}/100", style=mom_style),
            "",
        )
        table.add_row(
            "Score Volatilidad",
            Text(f"{vol.score:.0f}/100", style=vol_s_style),
            "",
        )

        self.console.print(table)

    def _print_risk_assessment(self, report: AnalysisReport) -> None:
        """Print risk assessment summary."""
        risk = report.risk

        # Traffic light summary
        text = Text()
        text.append("SEMAFORO DE RIESGOS\n\n", style="bold")

        text.append(f"  ROJO ({len(risk.red_flags)} senales):\n", style="bold red")
        for f in risk.red_flags:
            text.append(f"    [{f.category}] {f.description}\n", style="red")

        text.append(f"\n  AMARILLO ({len(risk.yellow_flags)} senales):\n", style="bold yellow")
        for f in risk.yellow_flags:
            text.append(f"    [{f.category}] {f.description}\n", style="yellow")

        text.append(f"\n  VERDE ({len(risk.green_flags)} senales):\n", style="bold green")
        for f in risk.green_flags:
            text.append(f"    [{f.category}] {f.description}\n", style="green")

        # Structural assessment
        text.append("\nANALISIS ESTRUCTURAL:\n", style="bold")
        text.append(f"  Low Float/High FDV: {'SI' if risk.low_float_high_fdv else 'NO'}\n",
                     style="red" if risk.low_float_high_fdv else "green")
        text.append(f"  Incentivos Mercenarios: {'SI' if risk.mercenary_incentives else 'NO'}\n",
                     style="red" if risk.mercenary_incentives else "green")
        text.append(f"  Riesgo Moral Hazard: {risk.moral_hazard_risk:.0f}/100\n",
                     style="red" if risk.moral_hazard_risk > 60 else "yellow" if risk.moral_hazard_risk > 40 else "green")
        text.append(f"  Estructura de Dumping: {'SI' if risk.dumping_structure else 'NO'}\n",
                     style="bold red" if risk.dumping_structure else "bold green")

        self.console.print(Panel(
            text,
            title="[bold]EVALUACION DE RIESGOS[/bold]",
            border_style="white",
            box=box.ROUNDED,
        ))

    def _print_final_verdict(self, report: AnalysisReport) -> None:
        """Print final verdict with score breakdown."""
        table = Table(
            title="PUNTUACION FINAL",
            box=box.DOUBLE,
            show_header=True,
            header_style="bold",
        )
        table.add_column("Dimension", style="bold")
        table.add_column("Score", justify="center")
        table.add_column("Peso", justify="center")
        table.add_column("Contribucion", justify="center")

        from config.settings import FINAL_SCORE_WEIGHTS as w
        dimensions = [
            ("Tokenomics", report.tokenomics.score, w["tokenomics"]),
            ("Cualitativo", report.qualitative.score, w["qualitative"]),
            ("Tecnico", report.technical.score, w["technical"]),
            ("Riesgo", report.risk.overall_risk_score, w["risk"]),
        ]

        for name, score, weight in dimensions:
            style = "green" if score >= 65 else "yellow" if score >= 45 else "red"
            contribution = score * weight
            table.add_row(
                name,
                Text(f"{score:.0f}/100", style=style),
                f"{weight:.0%}",
                f"{contribution:.1f}",
            )

        table.add_row("", "", "", "")

        verdict_colors = {
            Verdict.STRONG_BUY: "bold green",
            Verdict.BUY: "green",
            Verdict.NEUTRAL: "yellow",
            Verdict.SELL: "red",
            Verdict.STRONG_SELL: "bold red",
        }
        color = verdict_colors.get(report.verdict, "white")
        table.add_row(
            Text("TOTAL", style="bold"),
            Text(f"{report.final_score:.1f}/100", style=color),
            "",
            Text(report.verdict.value, style=color),
        )

        self.console.print(table)

        # Conclusion
        if report.risk.dumping_structure:
            conclusion = "Estructura disenada para DUMPING - alto riesgo de venta masiva por insiders."
        elif report.final_score >= 65:
            conclusion = "Estructura orientada a crecimiento a largo plazo con incentivos alineados."
        elif report.final_score >= 45:
            conclusion = "Estructura mixta - requiere monitoreo continuo de metricas clave."
        else:
            conclusion = "Estructura desfavorable - multiples senales de riesgo detectadas."

        self.console.print(Panel(
            Text(conclusion, style="bold"),
            title="[bold]CONCLUSION[/bold]",
            border_style=color.replace("bold ", ""),
        ))

    def _print_disclaimer(self, report: AnalysisReport) -> None:
        """Print disclaimer."""
        self.console.print(Panel(
            Text(report.disclaimer, style="dim italic"),
            border_style="dim",
            box=box.MINIMAL,
        ))
