"""
Risk manager for the Delta-Neutral Arbitrage Bot.
Evaluates positions against 3 active rules and scores opportunities.
Calibrated for capital < $1,000 per operation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from config import RISK, NADO_TAKER, EXCHANGE_01_TAKER

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Position dataclass
# ---------------------------------------------------------------------------
@dataclass
class Position:
    """Represents a delta-neutral position across two protocols."""

    id: str
    pair: str
    long_protocol: str
    short_protocol: str
    long_size_usd: float
    short_size_usd: float
    long_size_tokens: float
    short_size_tokens: float
    long_entry_price: float
    short_entry_price: float
    long_liq_price: float
    short_liq_price: float
    total_capital_usd: float
    leverage: float
    entry_funding_apr: float
    open_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    funding_collected_usd: float = 0.0
    fees_paid_usd: float = 0.0
    funding_inversions_count: int = 0
    status: str = "open"

    @property
    def age_hours(self) -> float:
        now = datetime.now(timezone.utc)
        ot = self.open_time if self.open_time.tzinfo else self.open_time.replace(tzinfo=timezone.utc)
        return (now - ot).total_seconds() / 3600

    @property
    def net_pnl_usd(self) -> float:
        return self.funding_collected_usd - self.fees_paid_usd

    @property
    def net_pnl_pct(self) -> float:
        if self.total_capital_usd <= 0:
            return 0.0
        return (self.net_pnl_usd / self.total_capital_usd) * 100

    @property
    def realized_apr(self) -> float:
        if self.age_hours <= 0 or self.total_capital_usd <= 0:
            return 0.0
        hourly_return = self.net_pnl_usd / self.total_capital_usd / self.age_hours
        return hourly_return * 8760 * 100

    def to_dict(self) -> dict:
        """Serialize to dict for persistence and WebSocket broadcast."""
        return {
            "id": self.id,
            "pair": self.pair,
            "long_protocol": self.long_protocol,
            "short_protocol": self.short_protocol,
            "long_size_usd": self.long_size_usd,
            "short_size_usd": self.short_size_usd,
            "long_size_tokens": self.long_size_tokens,
            "short_size_tokens": self.short_size_tokens,
            "long_entry_price": self.long_entry_price,
            "short_entry_price": self.short_entry_price,
            "long_liq_price": self.long_liq_price,
            "short_liq_price": self.short_liq_price,
            "total_capital_usd": self.total_capital_usd,
            "leverage": self.leverage,
            "entry_funding_apr": self.entry_funding_apr,
            "open_time": self.open_time.isoformat(),
            "funding_collected_usd": self.funding_collected_usd,
            "fees_paid_usd": self.fees_paid_usd,
            "funding_inversions_count": self.funding_inversions_count,
            "status": self.status,
            "age_hours": round(self.age_hours, 2),
            "net_pnl_usd": round(self.net_pnl_usd, 4),
            "net_pnl_pct": round(self.net_pnl_pct, 4),
            "realized_apr": round(self.realized_apr, 2),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        """Deserialize from dict."""
        open_time = d.get("open_time", datetime.now(timezone.utc).isoformat())
        if isinstance(open_time, str):
            open_time = datetime.fromisoformat(open_time)
        if open_time.tzinfo is None:
            open_time = open_time.replace(tzinfo=timezone.utc)
        return cls(
            id=d["id"],
            pair=d["pair"],
            long_protocol=d["long_protocol"],
            short_protocol=d["short_protocol"],
            long_size_usd=d["long_size_usd"],
            short_size_usd=d["short_size_usd"],
            long_size_tokens=d["long_size_tokens"],
            short_size_tokens=d["short_size_tokens"],
            long_entry_price=d["long_entry_price"],
            short_entry_price=d["short_entry_price"],
            long_liq_price=d["long_liq_price"],
            short_liq_price=d["short_liq_price"],
            total_capital_usd=d["total_capital_usd"],
            leverage=d["leverage"],
            entry_funding_apr=d["entry_funding_apr"],
            open_time=open_time,
            funding_collected_usd=d.get("funding_collected_usd", 0.0),
            fees_paid_usd=d.get("fees_paid_usd", 0.0),
            funding_inversions_count=d.get("funding_inversions_count", 0),
            status=d.get("status", "open"),
        )


# ---------------------------------------------------------------------------
# Risk signal
# ---------------------------------------------------------------------------
@dataclass
class RiskSignal:
    """Signal emitted by the risk manager for a given position."""

    should_close: bool
    reason: str
    urgency: str   # "critical" | "high" | "medium" | "low"
    details: dict
    action_message: str


# ---------------------------------------------------------------------------
# Risk manager
# ---------------------------------------------------------------------------
class RiskManager:
    """Evaluates positions and opportunities according to calibrated rules."""

    def __init__(self) -> None:
        self.risk = RISK

    # -----------------------------------------------------------------------
    # Position evaluation
    # -----------------------------------------------------------------------
    def evaluate_position(
        self,
        pos: Position,
        current_funding_hourly_pct: float,
        long_price: float,
        short_price: float,
    ) -> Optional[RiskSignal]:
        """Evaluate a position against all risk rules in priority order.

        Returns a RiskSignal if action is needed, None if position is healthy.
        """
        # RULE 1 — Funding sign inversion
        signal = self._check_funding_inversion(pos, current_funding_hourly_pct)
        if signal is not None:
            return signal

        # RULE 2 — Stop loss by PnL
        signal = self._check_stop_loss(pos)
        if signal is not None:
            return signal

        # RULE 3 (alert) — Liquidation proximity
        signal = self._check_liquidation(pos, long_price, short_price)
        if signal is not None:
            return signal

        # RULE 4 — Position expired
        signal = self._check_expiration(pos)
        if signal is not None:
            return signal

        return None

    def _check_funding_inversion(
        self, pos: Position, current_funding_hourly_pct: float
    ) -> Optional[RiskSignal]:
        if self.risk.STOP_IF_FUNDING_INVERTS and current_funding_hourly_pct < 0:
            pos.funding_inversions_count += 1
            if pos.funding_inversions_count >= self.risk.FUNDING_INVERSION_CHECKS:
                logger.warning(
                    "Funding inverted %dx for %s — closing",
                    pos.funding_inversions_count,
                    pos.id,
                )
                return RiskSignal(
                    should_close=True,
                    reason="FUNDING_INVERTIDO",
                    urgency="critical",
                    details={
                        "rate": current_funding_hourly_pct,
                        "checks": pos.funding_inversions_count,
                    },
                    action_message=(
                        f"Funding negativo confirmado {pos.funding_inversions_count}x. "
                        "Cerrando posicion inmediatamente."
                    ),
                )
            else:
                logger.info(
                    "Funding negative for %s (%d/%d checks)",
                    pos.id,
                    pos.funding_inversions_count,
                    self.risk.FUNDING_INVERSION_CHECKS,
                )
                return RiskSignal(
                    should_close=False,
                    reason="FUNDING_NEGATIVO_ADVERTENCIA",
                    urgency="high",
                    details={
                        "rate": current_funding_hourly_pct,
                        "checks": pos.funding_inversions_count,
                        "needed": self.risk.FUNDING_INVERSION_CHECKS,
                    },
                    action_message=(
                        f"Funding negativo "
                        f"({pos.funding_inversions_count}/{self.risk.FUNDING_INVERSION_CHECKS} confirmaciones)"
                    ),
                )
        else:
            pos.funding_inversions_count = 0
            return None

    def _check_stop_loss(self, pos: Position) -> Optional[RiskSignal]:
        if pos.net_pnl_pct < -self.risk.STOP_LOSS_PNL_PCT:
            logger.warning(
                "Stop loss triggered for %s: PnL %.2f%%",
                pos.id,
                pos.net_pnl_pct,
            )
            return RiskSignal(
                should_close=True,
                reason="STOP_LOSS",
                urgency="critical",
                details={
                    "pnl_pct": pos.net_pnl_pct,
                    "pnl_usd": pos.net_pnl_usd,
                    "threshold": -self.risk.STOP_LOSS_PNL_PCT,
                },
                action_message=(
                    f"Stop loss activado: PnL {pos.net_pnl_pct:.2f}% "
                    f"(limite: -{self.risk.STOP_LOSS_PNL_PCT}%)"
                ),
            )
        return None

    def _check_liquidation(
        self, pos: Position, long_price: float, short_price: float
    ) -> Optional[RiskSignal]:
        if long_price <= 0 or short_price <= 0:
            return None

        long_dist_pct = (long_price - pos.long_liq_price) / long_price * 100
        short_dist_pct = (pos.short_liq_price - short_price) / short_price * 100
        min_dist = min(long_dist_pct, short_dist_pct)

        if min_dist < self.risk.LIQUIDATION_BUFFER_PCT:
            logger.critical(
                "Liquidation proximity alert for %s: %.1f%% distance",
                pos.id,
                min_dist,
            )
            return RiskSignal(
                should_close=False,
                reason="ALERTA_LIQ",
                urgency="critical",
                details={
                    "long_dist_pct": round(long_dist_pct, 2),
                    "short_dist_pct": round(short_dist_pct, 2),
                    "min_dist_pct": round(min_dist, 2),
                },
                action_message=(
                    f"LIQUIDACION CERCANA: {min_dist:.1f}% de distancia. "
                    "REVISAR INMEDIATAMENTE."
                ),
            )
        return None

    def _check_expiration(self, pos: Position) -> Optional[RiskSignal]:
        if pos.age_hours > self.risk.MAX_POSITION_AGE_HOURS:
            logger.info("Position %s expired (%.1fh)", pos.id, pos.age_hours)
            return RiskSignal(
                should_close=True,
                reason="EXPIRADA",
                urgency="medium",
                details={
                    "age_hours": round(pos.age_hours, 2),
                    "max_hours": self.risk.MAX_POSITION_AGE_HOURS,
                },
                action_message=(
                    f"Posicion supero {self.risk.MAX_POSITION_AGE_HOURS}h. Cerrando."
                ),
            )
        return None

    # -----------------------------------------------------------------------
    # Opportunity evaluation
    # -----------------------------------------------------------------------
    def evaluate_opportunity(
        self,
        pair: str,
        funding_apr_nado: float,
        funding_apr_01: float,
        spread_nado_pct: float,
        spread_01_pct: float,
        depth_nado_usd: float,
        depth_01_usd: float,
    ) -> dict:
        """Score and filter an arbitrage opportunity.

        Returns a dict with viability assessment and all computed metrics.
        """
        # Determine direction: long where funding is lower, short where higher
        if funding_apr_nado >= funding_apr_01:
            long_p, short_p = "01", "nado"
            funding_captured_apr = funding_apr_nado
            long_fee_taker = EXCHANGE_01_TAKER
            short_fee_taker = NADO_TAKER
        else:
            long_p, short_p = "nado", "01"
            funding_captured_apr = funding_apr_01
            long_fee_taker = NADO_TAKER
            short_fee_taker = EXCHANGE_01_TAKER

        # Round-trip cost: 4 taker operations (open+close for each leg)
        total_fee_pct = (long_fee_taker + short_fee_taker) * 2  # 0.18%
        total_spread_pct = spread_nado_pct + spread_01_pct
        total_cost_pct = total_fee_pct + total_spread_pct

        # Break-even in hours
        hourly_funding_pct = funding_captured_apr / (365 * 24) if funding_captured_apr > 0 else 0
        if hourly_funding_pct > 0:
            breakeven_hours = total_cost_pct / hourly_funding_pct
        else:
            breakeven_hours = float("inf")

        # Net APR assuming hold for breakeven * 1.5
        hold_hours = max(breakeven_hours * 1.5, 1)
        if hold_hours > 0:
            net_apr = funding_captured_apr - (total_fee_pct * (365 * 24 / hold_hours))
        else:
            net_apr = 0.0

        # Score — weighted for small capital
        score = 0.0

        # APR weight 60%: max 60pts if Net APR >= 50%
        if net_apr > 0:
            score += min(net_apr / 50 * 60, 60)

        # Spread weight 25%: max 25pts if total spread = 0
        if total_spread_pct <= self.risk.MAX_SPREAD_PCT:
            score += max(0, (self.risk.MAX_SPREAD_PCT - total_spread_pct) / self.risk.MAX_SPREAD_PCT * 25)

        # Liquidity weight 15%: max 15pts if liquidity >= $20k
        min_depth = min(depth_nado_usd, depth_01_usd)
        score += min(min_depth / 20000 * 15, 15)

        score = round(score, 1)

        # Viability check — all filters must pass
        rejection_reasons = []
        if net_apr < self.risk.MIN_NET_APR_PCT:
            rejection_reasons.append(f"Net APR {net_apr:.1f}% < {self.risk.MIN_NET_APR_PCT}%")
        if total_spread_pct > self.risk.MAX_SPREAD_PCT:
            rejection_reasons.append(f"Spread {total_spread_pct:.4f}% > {self.risk.MAX_SPREAD_PCT}%")
        if score < self.risk.MIN_OPPORTUNITY_SCORE:
            rejection_reasons.append(f"Score {score:.1f} < {self.risk.MIN_OPPORTUNITY_SCORE}")
        if breakeven_hours > self.risk.MAX_BREAKEVEN_HOURS:
            rejection_reasons.append(f"Break-even {breakeven_hours:.0f}h > {self.risk.MAX_BREAKEVEN_HOURS}h")
        min_required_apr = self.risk.MIN_FUNDING_HOURLY_PCT * 365 * 24
        if funding_captured_apr < min_required_apr:
            rejection_reasons.append(
                f"Funding APR {funding_captured_apr:.1f}% < {min_required_apr:.1f}%"
            )

        is_viable = len(rejection_reasons) == 0

        result = {
            "pair": pair,
            "long_protocol": long_p,
            "short_protocol": short_p,
            "funding_apr_nado": round(funding_apr_nado, 2),
            "funding_apr_01": round(funding_apr_01, 2),
            "funding_captured_apr": round(funding_captured_apr, 2),
            "hourly_funding_pct": round(hourly_funding_pct, 6),
            "total_fee_pct": round(total_fee_pct, 4),
            "total_spread_pct": round(total_spread_pct, 4),
            "total_cost_pct": round(total_cost_pct, 4),
            "net_apr": round(net_apr, 2),
            "breakeven_hours": round(breakeven_hours, 1) if breakeven_hours != float("inf") else 9999,
            "score": score,
            "is_viable": is_viable,
            "rejection_reason": "; ".join(rejection_reasons) if rejection_reasons else None,
        }

        if is_viable:
            logger.info(
                "Viable opportunity: %s score=%.1f net_apr=%.1f%% breakeven=%.0fh",
                pair, score, net_apr, breakeven_hours,
            )
        else:
            logger.debug(
                "Rejected opportunity: %s — %s",
                pair, result["rejection_reason"],
            )

        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    rm = RiskManager()

    print("=== Opportunity Evaluation Test ===")
    opp = rm.evaluate_opportunity(
        pair="ETH-PERP",
        funding_apr_nado=42.0,
        funding_apr_01=35.0,
        spread_nado_pct=0.02,
        spread_01_pct=0.02,
        depth_nado_usd=25000,
        depth_01_usd=18000,
    )
    for k, v in opp.items():
        print(f"  {k}: {v}")

    print("\n=== Position Risk Evaluation Test ===")
    pos = Position(
        id="ETH-001",
        pair="ETH-PERP",
        long_protocol="01",
        short_protocol="nado",
        long_size_usd=225.0,
        short_size_usd=225.0,
        long_size_tokens=0.0693,
        short_size_tokens=0.0693,
        long_entry_price=3245.50,
        short_entry_price=3248.20,
        long_liq_price=2187.0,
        short_liq_price=4890.0,
        total_capital_usd=450.0,
        leverage=2.0,
        entry_funding_apr=39.4,
        funding_collected_usd=2.10,
        fees_paid_usd=0.41,
    )
    signal = rm.evaluate_position(pos, 0.0045, 3250.0, 3252.0)
    if signal:
        print(f"  Signal: {signal.reason} — {signal.action_message}")
    else:
        print("  Position OK — no risk signal")
