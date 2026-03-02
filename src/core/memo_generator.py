"""
BSB Capital - Investment Memo Generator
Generates institutional-grade investment analysis documents following
the template structure from Multicoin Capital, Paradigm, and a16z crypto.

Produces a complete 10-section investment memo with:
I. Resumen Ejecutivo
II. Contexto de Mercado
III. Deep Dive de Protocolo/Producto
IV. Analisis de Tokenomics
V. Evaluacion de Equipo
VI. Analisis Competitivo y Moats
VII. Modelo Financiero
VIII. Analisis de Riesgo
IX. Bull / Base / Bear Case
X. Recomendacion y Position Sizing
"""

from datetime import datetime
from typing import Optional

from src.models.schemas import (
    TokenMarketData,
    TokenType,
    TokenomicsAnalysis,
    QualitativeAnalysis,
    TechnicalAnalysis,
    RiskAssessment,
    Verdict,
)
from src.fundamental.advanced_scoring import (
    AdvancedScoring,
    _fmt_num,
)


class MemoGenerator:
    """Generates complete investment memo documents."""

    def generate(
        self,
        token: TokenMarketData,
        community_data: dict,
        tokenomics: TokenomicsAnalysis,
        qualitative: QualitativeAnalysis,
        technical: TechnicalAnalysis,
        risk: RiskAssessment,
        advanced: AdvancedScoring,
        final_score: float,
        verdict: Verdict,
    ) -> dict:
        """Generate complete investment memo as structured data."""
        memo = {
            "metadata": self._metadata(token, advanced, final_score, verdict),
            "sections": [
                self._section_executive_summary(
                    token, tokenomics, advanced, final_score, verdict, risk
                ),
                self._section_market_context(token, community_data),
                self._section_protocol_deep_dive(
                    token, community_data, tokenomics, advanced
                ),
                self._section_tokenomics(token, tokenomics, advanced),
                self._section_team(qualitative, community_data),
                self._section_competitive_moats(token, advanced, qualitative),
                self._section_financial_model(
                    token, tokenomics, advanced, technical
                ),
                self._section_risk_analysis(risk, tokenomics, advanced),
                self._section_scenarios(token, advanced, final_score, verdict),
                self._section_recommendation(
                    token, advanced, final_score, verdict, risk
                ),
            ],
            "scoring_summary": self._scoring_summary(
                tokenomics, qualitative, technical, risk, advanced, final_score
            ),
            "glossary": self._glossary_items(),
            "disclaimer": (
                "Este analisis es educativo y no constituye consejo financiero. "
                "Basado en datos disponibles publicamente y modelos estimativos. "
                "Los datos on-chain reales pueden diferir de las estimaciones. "
                "Realice su propia investigacion (DYOR) antes de tomar decisiones de inversion."
            ),
        }
        return memo

    # ------------------------------------------------------------------
    # METADATA
    # ------------------------------------------------------------------

    def _metadata(
        self,
        token: TokenMarketData,
        advanced: AdvancedScoring,
        final_score: float,
        verdict: Verdict,
    ) -> dict:
        return {
            "title": f"Investment Memo: {token.name} ({token.symbol})",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "token_name": token.name,
            "token_symbol": token.symbol,
            "token_type": token.token_type.value,
            "price": token.price_usd,
            "market_cap": token.market_cap,
            "composite_score": round(advanced.composite_score, 1),
            "conviction_tier": advanced.conviction_tier,
            "verdict": verdict.value,
            "final_score": round(final_score, 1),
        }

    # ------------------------------------------------------------------
    # I. RESUMEN EJECUTIVO
    # ------------------------------------------------------------------

    def _section_executive_summary(
        self,
        token: TokenMarketData,
        tokenomics: TokenomicsAnalysis,
        advanced: AdvancedScoring,
        final_score: float,
        verdict: Verdict,
        risk: RiskAssessment,
    ) -> dict:
        # Build thesis
        strengths = []
        risks_list = []

        td = advanced.tokenomics_dimensions
        if td.supply_mechanics >= 4:
            strengths.append("supply mechanics solida")
        if td.value_accrual >= 4:
            strengths.append("fuerte acumulacion de valor")
        if td.utility >= 4:
            strengths.append("utilidad multi-dimensional")

        qd = advanced.qualitative_dimensions
        if qd.team >= 70:
            strengths.append("equipo de alto calibre")
        if qd.competitive_moat >= 70:
            strengths.append("moat competitivo significativo")
        if qd.product_market_fit >= 70:
            strengths.append("product-market fit demostrado")

        if advanced.real_yield.is_real_yield:
            strengths.append("Real Yield positivo")

        if risk.dumping_structure:
            risks_list.append("estructura de dumping detectada")
        if risk.mercenary_incentives:
            risks_list.append("incentivos mercenarios")
        if advanced.velocity.velocity_risk in ("high", "critical"):
            risks_list.append("Token Velocity Problem sin resolver")
        if tokenomics.fdv_mcap_ratio > 5:
            risks_list.append(f"FDV/MCap elevado ({tokenomics.fdv_mcap_ratio:.1f}x)")
        if advanced.red_flags.is_disqualified:
            risks_list.append("multiples red flags auto-descalificadoras")

        thesis = _build_thesis(token, strengths, risks_list, verdict)

        return {
            "id": "executive_summary",
            "title": "I. Resumen Ejecutivo",
            "content": {
                "thesis": thesis,
                "conviction_drivers": strengths[:4] if strengths else ["Datos insuficientes"],
                "key_risks": risks_list[:4] if risks_list else ["Sin riesgos criticos detectados"],
                "composite_score": round(advanced.composite_score, 1),
                "conviction_tier": advanced.conviction_tier,
                "verdict": verdict.value,
                "price": f"${token.price_usd:,.2f}" if token.price_usd >= 1 else f"${token.price_usd:.6f}",
                "market_cap": _fmt_num(token.market_cap),
                "fdv": _fmt_num(token.fully_diluted_valuation),
            },
        }

    # ------------------------------------------------------------------
    # II. CONTEXTO DE MERCADO
    # ------------------------------------------------------------------

    def _section_market_context(
        self, token: TokenMarketData, community_data: dict
    ) -> dict:
        categories = community_data.get("categories", [])
        desc = community_data.get("description", "")

        sector_context = _get_sector_context(token.token_type, categories)

        return {
            "id": "market_context",
            "title": "II. Contexto de Mercado",
            "content": {
                "macro_thesis": sector_context["macro"],
                "sector": token.token_type.value,
                "categories": categories,
                "tam_analysis": sector_context["tam"],
                "competitive_landscape": sector_context["landscape"],
                "regulatory_context": sector_context["regulatory"],
                "description": desc,
            },
        }

    # ------------------------------------------------------------------
    # III. DEEP DIVE PROTOCOLO
    # ------------------------------------------------------------------

    def _section_protocol_deep_dive(
        self,
        token: TokenMarketData,
        community_data: dict,
        tokenomics: TokenomicsAnalysis,
        advanced: AdvancedScoring,
    ) -> dict:
        desc = community_data.get("description", "")

        pmf_evidence = []
        if advanced.real_yield.is_real_yield:
            pmf_evidence.append(f"Real Yield positivo ({advanced.real_yield.real_yield_pct:.1f}%)")
        if tokenomics.utility.has_real_demand:
            pmf_evidence.append(f"Demanda intrinseca: {tokenomics.utility.description}")
        if advanced.qualitative_dimensions.product_market_fit >= 60:
            pmf_evidence.append("Score de PMF favorable")
        if not pmf_evidence:
            pmf_evidence.append("Evidencia de PMF limitada o no concluyente")

        return {
            "id": "protocol_deep_dive",
            "title": "III. Deep Dive de Protocolo/Producto",
            "content": {
                "description": desc,
                "architecture": _get_architecture_notes(token.token_type),
                "pmf_evidence": pmf_evidence,
                "pmf_score": round(advanced.qualitative_dimensions.product_market_fit, 1),
                "pmf_detail": advanced.qualitative_dimensions.pmf_detail,
                "utility_types": tokenomics.utility.description,
                "velocity_analysis": {
                    "velocity": round(advanced.velocity.estimated_velocity, 1),
                    "risk": advanced.velocity.velocity_risk,
                    "sinks": advanced.velocity.velocity_sinks,
                    "detail": advanced.velocity.detail,
                },
                "value_accrual": {
                    "model": advanced.value_accrual.accrual_model,
                    "mechanisms": advanced.value_accrual.mechanisms,
                    "detail": advanced.value_accrual.detail,
                },
            },
        }

    # ------------------------------------------------------------------
    # IV. TOKENOMICS
    # ------------------------------------------------------------------

    def _section_tokenomics(
        self,
        token: TokenMarketData,
        tokenomics: TokenomicsAnalysis,
        advanced: AdvancedScoring,
    ) -> dict:
        td = advanced.tokenomics_dimensions
        return {
            "id": "tokenomics",
            "title": "IV. Analisis de Tokenomics",
            "content": {
                "supply": {
                    "circulating": f"{token.circulating_supply:,.0f}",
                    "total": f"{token.total_supply:,.0f}",
                    "max": f"{token.max_supply:,.0f}" if token.max_supply else "Sin limite",
                    "supply_ratio": f"{tokenomics.inflation.supply_ratio*100:.1f}%",
                    "inflation_rate": f"{tokenomics.inflation.current_inflation_rate:.1f}%",
                    "max_inflation": f"{tokenomics.inflation.max_inflation:.1f}%",
                },
                "distribution": {
                    "team": f"{tokenomics.distribution.team_allocation:.1f}%",
                    "investors": f"{tokenomics.distribution.investor_allocation:.1f}%",
                    "community": f"{tokenomics.distribution.community_allocation:.1f}%",
                    "ecosystem": f"{tokenomics.distribution.ecosystem_allocation:.1f}%",
                    "treasury": f"{tokenomics.distribution.treasury_allocation:.1f}%",
                    "insiders_total": f"{tokenomics.distribution.insider_percentage:.1f}%",
                },
                "vesting": {
                    "duration": f"{tokenomics.vesting.vesting_duration_months} meses",
                    "cliff": f"{tokenomics.vesting.cliff_months} meses",
                    "tge_unlock": f"{tokenomics.vesting.tge_unlock_percentage:.1f}%",
                },
                "fdv_analysis": {
                    "fdv": _fmt_num(token.fully_diluted_valuation),
                    "mcap": _fmt_num(token.market_cap),
                    "ratio": f"{tokenomics.fdv_mcap_ratio:.1f}x",
                    "interpretation": (
                        "ALERTA: ratio elevado senala dilucion masiva futura"
                        if tokenomics.fdv_mcap_ratio > 5
                        else "Ratio saludable"
                    ),
                },
                "real_yield": {
                    "protocol_revenue": _fmt_num(advanced.real_yield.estimated_protocol_revenue),
                    "emissions_value": _fmt_num(advanced.real_yield.estimated_token_emissions_value),
                    "real_yield_pct": (
                        f"{advanced.real_yield.real_yield_pct:.1f}%"
                        if advanced.real_yield.real_yield_pct is not None
                        else "N/D"
                    ),
                    "sustainability": advanced.real_yield.yield_sustainability,
                    "detail": advanced.real_yield.detail,
                },
                "dimension_scores": {
                    "supply_mechanics": {"score": td.supply_mechanics, "detail": td.supply_detail},
                    "distribution": {"score": td.distribution, "detail": td.distribution_detail},
                    "utility": {"score": td.utility, "detail": td.utility_detail},
                    "value_accrual": {"score": td.value_accrual, "detail": td.value_accrual_detail},
                    "governance": {"score": td.governance, "detail": td.governance_detail},
                    "vesting_unlocks": {"score": td.vesting_unlocks, "detail": td.vesting_detail},
                },
                "weighted_score": round(td.weighted_score, 1),
                "nvt": {
                    "ratio": advanced.nvt_ratio,
                    "signal": advanced.nvt_signal,
                },
                "metcalfe": {
                    "ratio": advanced.metcalfe_value_ratio,
                    "signal": advanced.metcalfe_signal,
                },
                "red_flags": {
                    "triggered": advanced.red_flags.triggered,
                    "disqualified": advanced.red_flags.is_disqualified,
                    "detail": advanced.red_flags.detail,
                },
            },
        }

    # ------------------------------------------------------------------
    # V. EQUIPO
    # ------------------------------------------------------------------

    def _section_team(
        self, qualitative: QualitativeAnalysis, community_data: dict
    ) -> dict:
        team = qualitative.team
        founders = community_data.get("founders", [])

        return {
            "id": "team_evaluation",
            "title": "V. Evaluacion de Equipo",
            "content": {
                "founders": founders if founders else ["No identificados"],
                "doxxed": team.founders_doxxed,
                "team_score": round(team.team_score, 1),
                "dev_activity": round(team.development_activity_score, 1),
                "commits_30d": team.github_commits_30d,
                "transparency": round(team.transparency_score, 1),
                "track_record": round(team.track_record_score, 1),
                "assessment": (
                    "Equipo solido con track record verificable y alta actividad de desarrollo"
                    if team.team_score >= 70
                    else "Equipo con capacidad moderada o informacion parcial"
                    if team.team_score >= 45
                    else "Datos insuficientes o equipo debil - riesgo elevado"
                ),
                "doxxed_note": (
                    "Equipo doxxed reduce riesgo de abandono (VCs institucionales lo exigen)"
                    if team.founders_doxxed
                    else "Equipo no doxxed - 'red flag significativa' segun VCs. "
                    "Sin consecuencias reputacionales por abandono."
                ),
            },
        }

    # ------------------------------------------------------------------
    # VI. MOATS
    # ------------------------------------------------------------------

    def _section_competitive_moats(
        self,
        token: TokenMarketData,
        advanced: AdvancedScoring,
        qualitative: QualitativeAnalysis,
    ) -> dict:
        qd = advanced.qualitative_dimensions
        vc = qualitative.vc

        return {
            "id": "competitive_moats",
            "title": "VI. Analisis Competitivo y Moats",
            "content": {
                "moat_score": round(qd.competitive_moat, 1),
                "moat_detail": qd.moat_detail,
                "liquidity_moat": token.volume_24h > 500e6,
                "network_effects": token.market_cap > 10e9,
                "switching_costs": advanced.value_accrual.ve_token_model,
                "brand_lindy": token.token_type == TokenType.L1,
                "ecosystem_score": round(qd.ecosystem_partners, 1),
                "ecosystem_detail": qd.ecosystem_detail,
                "tier1_vcs": vc.tier1_investors,
                "partners": vc.strategic_partners,
                "composability_note": (
                    "Ecosistema con composabilidad activa crea switching costs reales. "
                    "Cambiar dependencia core requiere investigacion, cambios de codigo, "
                    "re-auditoria y migracion de liquidez (Mint Ventures)."
                    if qd.competitive_moat >= 60
                    else "Moat limitado. Codigo open-source permite forks en dias. "
                    "Alliance DAO clasifica los mejores crypto en ~5/10 de moat."
                ),
            },
        }

    # ------------------------------------------------------------------
    # VII. MODELO FINANCIERO
    # ------------------------------------------------------------------

    def _section_financial_model(
        self,
        token: TokenMarketData,
        tokenomics: TokenomicsAnalysis,
        advanced: AdvancedScoring,
        technical: TechnicalAnalysis,
    ) -> dict:
        qm = advanced.quantitative_metrics
        return {
            "id": "financial_model",
            "title": "VII. Modelo Financiero",
            "content": {
                "quantitative_score": round(qm.weighted_score, 1),
                "metrics": {
                    "pf_ratio": {"score": round(qm.pf_ratio_score, 1), "detail": qm.pf_detail},
                    "ptvl": {"score": round(qm.ptvl_score, 1), "detail": qm.ptvl_detail},
                    "revenue_growth": {"score": round(qm.revenue_growth_score, 1), "detail": qm.revenue_detail},
                    "dau_growth": {"score": round(qm.dau_growth_score, 1), "detail": qm.dau_detail},
                    "developer_activity": {"score": round(qm.developer_activity_score, 1), "detail": qm.dev_detail},
                    "real_yield": {"score": round(qm.real_yield_score, 1), "detail": qm.yield_detail},
                    "smart_money": {"score": round(qm.smart_money_score, 1), "detail": qm.smart_money_detail},
                    "supply_concentration": {"score": round(qm.supply_concentration_score, 1), "detail": qm.concentration_detail},
                },
                "technical_overlay": {
                    "trend": technical.momentum.trend.value,
                    "volatility_regime": technical.volatility.market_regime.value,
                    "sharpe": round(technical.volatility.sharpe_ratio, 2) if technical.volatility.sharpe_ratio else None,
                    "drawdown_30d": round(technical.volatility.max_drawdown_30d, 1),
                },
            },
        }

    # ------------------------------------------------------------------
    # VIII. RIESGOS
    # ------------------------------------------------------------------

    def _section_risk_analysis(
        self,
        risk: RiskAssessment,
        tokenomics: TokenomicsAnalysis,
        advanced: AdvancedScoring,
    ) -> dict:
        risk_categories = {
            "smart_contract": {
                "level": "medio",
                "detail": "Riesgo inherente de smart contracts (reentrancy, overflow). Mitigacion: auditorias, bug bounties.",
            },
            "market_liquidity": {
                "level": "bajo" if not risk.low_float_high_fdv else "alto",
                "detail": (
                    "Low Float / High FDV detectado - riesgo de liquidez en salidas"
                    if risk.low_float_high_fdv
                    else "Liquidez adecuada para el market cap actual"
                ),
            },
            "tokenomics_risk": {
                "level": (
                    "alto"
                    if risk.dumping_structure
                    else "medio"
                    if risk.mercenary_incentives
                    else "bajo"
                ),
                "detail": (
                    f"Estructura de dumping detectada. Moral hazard: {risk.moral_hazard_risk:.0f}/100"
                    if risk.dumping_structure
                    else f"Moral hazard: {risk.moral_hazard_risk:.0f}/100"
                ),
            },
            "regulatory": {
                "level": "medio",
                "detail": (
                    "Landscape regulatorio en evolucion: MiCA (UE), GENIUS Act y CLARITY Act (EE.UU.). "
                    "Clasificacion como security puede impactar significativamente."
                ),
            },
            "governance": {
                "level": (
                    "alto"
                    if tokenomics.distribution.insider_percentage > 40
                    else "medio"
                ),
                "detail": (
                    "Participacion promedio en gobernanza crypto es ~6.3% (Cong et al. 2025). "
                    "DAOs mas grandes tienden a ser mas centralizadas."
                ),
            },
            "velocity": {
                "level": advanced.velocity.velocity_risk,
                "detail": advanced.velocity.detail,
            },
        }

        return {
            "id": "risk_analysis",
            "title": "VIII. Analisis de Riesgo",
            "content": {
                "overall_risk_score": round(risk.overall_risk_score, 1),
                "red_flags": [
                    {"category": f.category, "description": f.description}
                    for f in risk.red_flags
                ],
                "yellow_flags": [
                    {"category": f.category, "description": f.description}
                    for f in risk.yellow_flags
                ],
                "green_flags": [
                    {"category": f.category, "description": f.description}
                    for f in risk.green_flags
                ],
                "risk_categories": risk_categories,
                "structural": {
                    "low_float_high_fdv": risk.low_float_high_fdv,
                    "mercenary_incentives": risk.mercenary_incentives,
                    "dumping_structure": risk.dumping_structure,
                    "moral_hazard": round(risk.moral_hazard_risk, 0),
                },
                "auto_disqualifiers": {
                    "triggered": advanced.red_flags.triggered,
                    "is_disqualified": advanced.red_flags.is_disqualified,
                },
            },
        }

    # ------------------------------------------------------------------
    # IX. SCENARIOS
    # ------------------------------------------------------------------

    def _section_scenarios(
        self,
        token: TokenMarketData,
        advanced: AdvancedScoring,
        final_score: float,
        verdict: Verdict,
    ) -> dict:
        price = token.price_usd
        ath = token.ath

        # Bull case
        bull_multiplier = min(ath / price, 5) if price > 0 else 2
        bull_target = price * bull_multiplier

        # Base case
        base_multiplier = max(1, bull_multiplier * 0.4)
        base_target = price * base_multiplier

        # Bear case
        bear_multiplier = max(0.3, 1 - abs(token.ath_change_percentage) / 200)
        bear_target = price * bear_multiplier

        # Probabilities based on score
        if final_score >= 70:
            bull_prob, base_prob, bear_prob = 30, 45, 25
        elif final_score >= 50:
            bull_prob, base_prob, bear_prob = 25, 40, 35
        else:
            bull_prob, base_prob, bear_prob = 15, 35, 50

        # Expected return
        expected = (
            bull_prob / 100 * (bull_multiplier - 1)
            + base_prob / 100 * (base_multiplier - 1)
            + bear_prob / 100 * (bear_multiplier - 1)
        )

        def _fmt_price(p):
            if p < 0.01:
                return f"${p:.6f}"
            if p < 1:
                return f"${p:.4f}"
            return f"${p:,.2f}"

        return {
            "id": "scenarios",
            "title": "IX. Bull / Base / Bear Case",
            "content": {
                "bull": {
                    "probability": f"{bull_prob}%",
                    "target_price": _fmt_price(bull_target),
                    "multiplier": f"{bull_multiplier:.1f}x",
                    "assumptions": [
                        "Maxima captura de mercado en el sector",
                        "Regulacion favorable y adopcion institucional",
                        "Network effects compuestos y crecimiento de developers",
                        "Revenue real creciente y Real Yield sostenible",
                    ],
                },
                "base": {
                    "probability": f"{base_prob}%",
                    "target_price": _fmt_price(base_target),
                    "multiplier": f"{base_multiplier:.1f}x",
                    "assumptions": [
                        "Adopcion moderada y posicion sostenible",
                        "Regulacion neutral sin impacto material",
                        "Competencia manejable, moat parcialmente efectivo",
                    ],
                },
                "bear": {
                    "probability": f"{bear_prob}%",
                    "target_price": _fmt_price(bear_target),
                    "multiplier": f"{bear_multiplier:.1f}x",
                    "assumptions": [
                        "Exploit de smart contract o fallo de seguridad",
                        "Crackdown regulatorio adverso",
                        "Competidor superior con vampire attack exitoso",
                        "Fallo tokenomico o espiral de desbloqueos",
                    ],
                },
                "expected_return": f"{expected*100:+.0f}%",
                "expected_multiplier": f"{1+expected:.2f}x",
            },
        }

    # ------------------------------------------------------------------
    # X. RECOMENDACION
    # ------------------------------------------------------------------

    def _section_recommendation(
        self,
        token: TokenMarketData,
        advanced: AdvancedScoring,
        final_score: float,
        verdict: Verdict,
        risk: RiskAssessment,
    ) -> dict:
        # Position sizing based on conviction
        if advanced.composite_score >= 80:
            sizing = "5-10% de allocacion crypto"
            strategy = "DCA agresivo en soportes tecnicos"
        elif advanced.composite_score >= 60:
            sizing = "2-5% de allocacion crypto"
            strategy = "DCA gradual con rebalanceo trimestral"
        elif advanced.composite_score >= 40:
            sizing = "0.5-2% de allocacion crypto (especulativo)"
            strategy = "Entrada condicional en catalizador especifico"
        else:
            sizing = "0% - No recomendado"
            strategy = "Solo observar o posicion de cobertura minima"

        exit_criteria = [
            "Deterioro de fundamentals (caida de revenue >50% QoQ)",
            "Cambio regulatorio adverso material",
            "Exploit de seguridad no resuelto",
            "Desviacion >25% del target allocation (trigger de rebalanceo)",
        ]

        if risk.dumping_structure:
            exit_criteria.insert(
                0, "PRIORITARIO: Estructura de dumping activa - monitorear vesting unlocks"
            )

        return {
            "id": "recommendation",
            "title": "X. Recomendacion y Position Sizing",
            "content": {
                "composite_score": round(advanced.composite_score, 1),
                "tokenomics_score": round(advanced.tokenomics_dimensions.weighted_score, 1),
                "qualitative_score": round(advanced.qualitative_dimensions.weighted_score, 1),
                "quantitative_score": round(advanced.quantitative_metrics.weighted_score, 1),
                "conviction_tier": advanced.conviction_tier,
                "verdict": verdict.value,
                "position_sizing": sizing,
                "entry_strategy": strategy,
                "exit_criteria": exit_criteria,
                "rebalance_trigger": "Desviacion >25% del target allocation",
                "formula": (
                    f"Tokenomics ({round(advanced.tokenomics_dimensions.weighted_score, 1)}) x 0.30 "
                    f"+ Cualitativo ({round(advanced.qualitative_dimensions.weighted_score, 1)}) x 0.35 "
                    f"+ Cuantitativo ({round(advanced.quantitative_metrics.weighted_score, 1)}) x 0.35 "
                    f"= {round(advanced.composite_score, 1)}/100"
                ),
            },
        }

    # ------------------------------------------------------------------
    # SCORING SUMMARY
    # ------------------------------------------------------------------

    def _scoring_summary(
        self,
        tokenomics: TokenomicsAnalysis,
        qualitative: QualitativeAnalysis,
        technical: TechnicalAnalysis,
        risk: RiskAssessment,
        advanced: AdvancedScoring,
        final_score: float,
    ) -> dict:
        td = advanced.tokenomics_dimensions
        qd = advanced.qualitative_dimensions
        qm = advanced.quantitative_metrics

        return {
            "tokenomics_dimensions": {
                "supply_mechanics": {"score": td.supply_mechanics, "max": 5, "weight": "20%"},
                "distribution": {"score": td.distribution, "max": 5, "weight": "20%"},
                "utility": {"score": td.utility, "max": 5, "weight": "20%"},
                "value_accrual": {"score": td.value_accrual, "max": 5, "weight": "15%"},
                "governance": {"score": td.governance, "max": 5, "weight": "10%"},
                "vesting_unlocks": {"score": td.vesting_unlocks, "max": 5, "weight": "15%"},
                "weighted_total": round(td.weighted_score, 1),
            },
            "qualitative_dimensions": {
                "team": {"score": round(qd.team, 1), "max": 100, "weight": "25%"},
                "product_market_fit": {"score": round(qd.product_market_fit, 1), "max": 100, "weight": "30%"},
                "ecosystem_partners": {"score": round(qd.ecosystem_partners, 1), "max": 100, "weight": "20%"},
                "competitive_moat": {"score": round(qd.competitive_moat, 1), "max": 100, "weight": "25%"},
                "weighted_total": round(qd.weighted_score, 1),
            },
            "quantitative_metrics": {
                "pf_ratio": {"score": round(qm.pf_ratio_score, 1), "weight": "15%"},
                "ptvl": {"score": round(qm.ptvl_score, 1), "weight": "10%"},
                "revenue_growth": {"score": round(qm.revenue_growth_score, 1), "weight": "15%"},
                "dau_growth": {"score": round(qm.dau_growth_score, 1), "weight": "10%"},
                "developer_activity": {"score": round(qm.developer_activity_score, 1), "weight": "10%"},
                "real_yield": {"score": round(qm.real_yield_score, 1), "weight": "15%"},
                "smart_money": {"score": round(qm.smart_money_score, 1), "weight": "10%"},
                "supply_concentration": {"score": round(qm.supply_concentration_score, 1), "weight": "15%"},
                "weighted_total": round(qm.weighted_score, 1),
            },
            "composite": {
                "tokenomics_weighted": round(td.weighted_score * 0.30, 1),
                "qualitative_weighted": round(qd.weighted_score * 0.35, 1),
                "quantitative_weighted": round(qm.weighted_score * 0.35, 1),
                "total": round(advanced.composite_score, 1),
            },
            "legacy_scores": {
                "tokenomics": round(tokenomics.score, 1),
                "qualitative": round(qualitative.score, 1),
                "technical": round(technical.score, 1),
                "risk": round(risk.overall_risk_score, 1),
                "final": round(final_score, 1),
            },
        }

    # ------------------------------------------------------------------
    # GLOSSARY
    # ------------------------------------------------------------------

    def _glossary_items(self) -> list[dict]:
        return [
            {"term": "Real Yield", "definition": "Rendimiento generado por revenue real del protocolo menos emisiones inflacionarias. Formula: (Protocol Revenue - Token Emissions) / Staked Value."},
            {"term": "Token Velocity Problem", "definition": "Critica de Kyle Samani (Multicoin 2017): sin mecanismos de retencion, la velocidad crece linealmente y el valor de red permanece estancado."},
            {"term": "NVT Ratio", "definition": "Network Value to Transactions (Willy Woo 2017). NVT = Market Cap / Vol. On-Chain diario. Analogo al P/E ratio. Alto = sobrevalorado."},
            {"term": "Metcalfe's Law", "definition": "Valor de red proporcional a n^1.69-2.0 (Peterson 2018). Exponent empirico de Wheatley et al. 2019."},
            {"term": "veToken", "definition": "Vote-Escrowed Token: tokens bloqueados 1-4 anos a cambio de poder de voto y fees. Arquetipo: veCRV de Curve Finance."},
            {"term": "MEV", "definition": "Maximal Extractable Value: valor extraible por productores de bloques reordenando transacciones."},
            {"term": "FDV", "definition": "Fully Diluted Valuation = Total Supply x Precio. Ratio FDV/MCap >8-10x es red flag severa."},
            {"term": "Velocity Sink", "definition": "Mecanismo que reduce velocidad de circulacion: staking, burns, lockups, revenue sharing."},
            {"term": "Vampire Attack", "definition": "Protocolo competidor ofrece incentivos agresivos para atraer liquidez/usuarios. SushiSwap vs Uniswap fue el caso paradigmatico."},
            {"term": "Protocol Sink", "definition": "Concepto de Chapter One: cuando otros developers construyen sobre tu infraestructura de forma fundamental e irremplazable."},
        ]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _build_thesis(
    token: TokenMarketData,
    strengths: list[str],
    risks: list[str],
    verdict: Verdict,
) -> str:
    if verdict in (Verdict.STRONG_BUY, Verdict.BUY):
        tone = f"{token.name} presenta una oportunidad de inversion favorable"
    elif verdict == Verdict.NEUTRAL:
        tone = f"{token.name} se encuentra en una posicion mixta"
    else:
        tone = f"{token.name} presenta multiples senales de precaucion"

    parts = [tone]
    if strengths:
        parts.append(f"respaldada por {', '.join(strengths[:3])}")
    if risks:
        parts.append(f"con riesgos clave en {', '.join(risks[:2])}")
    return ". ".join(parts) + "."


def _get_sector_context(token_type: TokenType, categories: list[str]) -> dict:
    contexts = {
        TokenType.L1: {
            "macro": (
                "Los L1 enfrentan un desafio estructural en 2025-2026: capturan 90% del market cap "
                "pero solo 12% de fees (vs 60% anteriormente). El valor migra de infraestructura "
                "a aplicaciones. Post-Merge ETH genera 3-5% APR por staking. "
                "Fidelity Research describe Fusaka como 'el upgrade mas convincente en anos'."
            ),
            "tam": "TAM de plataformas smart contract: $500B-2T (estimacion a16z State of Crypto 2025)",
            "landscape": "Competencia intensa entre ETH, SOL, y emergentes. Ethereum lidera con 31,869 devs activos (2x Solana). EVM domina con 8,925 devs vs 2,499 SVM.",
            "regulatory": "MiCA implementado en UE. GENIUS Act y CLARITY Act en tramite en EE.UU. Bitcoin clasificado como commodity, ETH en zona gris.",
        },
        TokenType.L2: {
            "macro": (
                "L2s capturan valor via sequencer fees y extraccion de MEV. "
                "Problema central: la mayoria cobra fees en ETH, no en token nativo. "
                "Base genera ~$185K revenue diario sin token. "
                "Based rollups como Taiko podrian resolver la acumulacion de valor en L1."
            ),
            "tam": "TAM de soluciones de escalado: $50-200B",
            "landscape": "Competencia entre Arbitrum, Optimism, Base, zkSync, Starknet. Ola de based rollups emergiendo.",
            "regulatory": "Menor escrutinio regulatorio que L1s, pero tokens de gobernanza pueden ser clasificados como securities.",
        },
        TokenType.DEFI: {
            "macro": (
                "DeFi emplea cuatro modelos de acumulacion: burns, distribuciones directas (GMX), "
                "vote-escrow + bribes (Curve), e hibridos (Hyperliquid). "
                "Participacion promedio en gobernanza es solo 6.3% (Cong et al. 2025). "
                "Blue chips DeFi funcionaron impecablemente en 2022 mientras CeFi colapsaba."
            ),
            "tam": "TVL DeFi total: ~$100B. Revenue anualizado top protocolos: $1-5B",
            "landscape": "Protocolo Sink: Uniswap, Aave, Curve son infraestructura base. Hyperliquid supero Uniswap + PancakeSwap en volumen.",
            "regulatory": "Fee switch de Uniswap activado con 99.9% aprobacion. Compra de MKR por Dragonfly/Paradigm ilustra riesgos de concentracion.",
        },
    }
    return contexts.get(
        token_type,
        {
            "macro": "Sector emergente con dinamicas de mercado en evolucion rapida.",
            "tam": "TAM en definicion segun adoption curves",
            "landscape": "Competencia abierta con barreras de entrada bajas por naturaleza open-source.",
            "regulatory": "Landscape regulatorio en desarrollo. Monitorear MiCA (UE) y legislacion EE.UU.",
        },
    )


def _get_architecture_notes(token_type: TokenType) -> str:
    notes = {
        TokenType.L1: (
            "Layer 1 blockchain con consenso propio. Acumula valor por cuatro vias: "
            "prima monetaria (store of value), seguridad (staking yields), "
            "gobernanza y fees/burns. Evaluacion de EIP-1559 dynamics y MEV."
        ),
        TokenType.L2: (
            "Layer 2 scaling solution. Captura valor via sequencer fees, "
            "derechos de gobernanza y extraccion de MEV. "
            "Evaluar dependencia del L1 subyacente."
        ),
        TokenType.DEFI: (
            "Protocolo DeFi. Evaluar mecanismos AMM, liquidez, composabilidad. "
            "Verificar auditorias de seguridad y historial de exploits."
        ),
    }
    return notes.get(token_type, "Arquitectura en evaluacion. Verificar documentacion tecnica.")
