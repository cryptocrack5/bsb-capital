"""
Main engine for the Delta-Neutral Arbitrage Bot.
Orchestrates monitoring, risk checks, position management, WebSocket dashboard,
and Telegram notifications.
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

import websockets
import websockets.server

from config import (
    RISK,
    NADO,
    EXCHANGE_01,
    DASHBOARD,
    NADO_TAKER,
    EXCHANGE_01_TAKER,
    MONITORED_PAIRS,
)
from risk_manager import Position, RiskManager
from nado_client import NadoClient
from exchange01_client import Exchange01Client
from telegram_bot import TelegramBot

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
try:
    import colorlog
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.root.handlers = [handler]
except ImportError:
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

logging.root.setLevel(logging.INFO)
logger = logging.getLogger("bot")

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POSITIONS_FILE = DATA_DIR / "positions.json"
HISTORY_FILE = DATA_DIR / "history.json"
STATE_FILE = DATA_DIR / "state.json"


class DeltaNeutralBot:
    """Main orchestrator for the delta-neutral funding rate arbitrage system."""

    def __init__(self) -> None:
        self.nado = NadoClient()
        self.exchange01 = Exchange01Client()
        self.risk_manager = RiskManager()
        self.telegram = TelegramBot()

        self.open_positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self.opportunities: List[dict] = []
        self.market_data: Dict[str, dict] = {}
        self.recent_logs: List[dict] = []

        self.paused: bool = False
        self._pos_counter: Dict[str, int] = {}
        self._ws_clients: Set[websockets.server.WebSocketServerProtocol] = set()
        self._running: bool = False
        self._funding_history: Dict[str, List[dict]] = {p: [] for p in MONITORED_PAIRS}

        # Daily stats
        self._daily_funding: float = 0.0
        self._daily_fees: float = 0.0
        self._daily_opps_seen: int = 0
        self._daily_opened: int = 0
        self._daily_closed: int = 0
        self._last_daily_reset: Optional[datetime] = None

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------
    async def initialize(self) -> None:
        """Initialize all components and load persisted state."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_state()

        # Init exchange clients
        nado_ok = False
        try:
            await self.nado.initialize()
            nado_ok = await self.nado.health_check()
        except Exception as exc:
            logger.error("Nado initialization failed: %s", exc)

        ex01_ok = self.exchange01.health_check()

        # Report balances
        if nado_ok:
            try:
                balance = await self.nado.get_balance()
                logger.info("Nado balance: $%.2f", balance)
            except Exception:
                pass
        if ex01_ok:
            try:
                balance = self.exchange01.get_balance()
                logger.info("01 Exchange balance: $%.2f", balance)
            except Exception:
                pass

        # Setup Telegram callbacks
        self.telegram.on_open_position = self._tg_open_position
        self.telegram.on_close_position = self._tg_close_position
        self.telegram.on_close_all = self._tg_close_all
        self.telegram.on_pause = self._tg_pause
        self.telegram.on_resume = self._tg_resume
        self.telegram.on_set_risk = self._tg_set_risk
        self.telegram.on_set_dryrun = self._tg_set_dryrun
        self.telegram.get_status = self._get_status_dict
        self.telegram.get_opportunities = lambda: self.opportunities
        self.telegram.get_positions = lambda: self.open_positions

        await self.telegram.start()
        await self.telegram.notify_system_start(nado_ok, ex01_ok)

        self._add_log("INFO", f"Bot inicializado. Nado: {'OK' if nado_ok else 'FAIL'}, "
                       f"01: {'OK' if ex01_ok else 'MOCK'}. Modo: {'DRY' if RISK.DRY_RUN else 'REAL'}")
        logger.info("Bot initialized — DRY_RUN=%s, pairs=%s", RISK.DRY_RUN, MONITORED_PAIRS)

    # -----------------------------------------------------------------------
    # Main run loop
    # -----------------------------------------------------------------------
    async def run(self) -> None:
        """Start all concurrent loops."""
        await self.initialize()
        self._running = True

        try:
            await asyncio.gather(
                self.monitor_loop(),
                self.risk_check_loop(),
                self.funding_accumulate_loop(),
                self.dashboard_ws_server(),
                self.daily_report_loop(),
            )
        except asyncio.CancelledError:
            logger.info("Bot shutdown requested")
        except Exception as exc:
            logger.error("Bot crashed: %s", exc, exc_info=True)
        finally:
            self._running = False
            await self.nado.close()
            await self.telegram.stop()
            await self._persist_state()
            logger.info("Bot stopped")

    # -----------------------------------------------------------------------
    # Monitor loop — every 30s
    # -----------------------------------------------------------------------
    async def monitor_loop(self) -> None:
        """Fetch market data and evaluate opportunities every cycle."""
        while self._running:
            try:
                await self._monitor_cycle()
            except Exception as exc:
                logger.error("Monitor cycle error: %s", exc, exc_info=True)
                self._add_log("ERROR", f"Error en monitor: {exc}")
            await asyncio.sleep(RISK.MONITOR_INTERVAL_SECONDS)

    async def _monitor_cycle(self) -> None:
        # Fetch funding rates from both protocols
        nado_rates: Dict[str, float] = {}
        ex01_rates: Dict[str, float] = {}

        try:
            nado_rates = await self.nado.get_funding_rates()
        except Exception as exc:
            logger.warning("Failed to get Nado rates: %s", exc)

        try:
            ex01_rates = self.exchange01.get_funding_rates()
        except Exception as exc:
            logger.warning("Failed to get 01 rates: %s", exc)

        # Fetch orderbooks for spread/depth
        new_opportunities: List[dict] = []
        for pair in MONITORED_PAIRS:
            try:
                nado_ob = await self.nado.get_orderbook(pair)
                ex01_ob = self.exchange01.get_orderbook(pair)

                funding_nado = nado_rates.get(pair, 0)
                funding_01 = ex01_rates.get(pair, 0)
                spread_nado = nado_ob.get("spread_pct", 0)
                spread_01 = ex01_ob.get("spread_pct", 0)
                depth_nado = nado_ob.get("depth_usd", 0)
                depth_01 = ex01_ob.get("depth_usd", 0)

                self.market_data[pair] = {
                    "funding_apr_nado": round(funding_nado, 2),
                    "funding_apr_01": round(funding_01, 2),
                    "spread_nado": round(spread_nado, 4),
                    "spread_01": round(spread_01, 4),
                    "price_nado": nado_ob.get("mid", 0),
                    "price_01": ex01_ob.get("mid", 0),
                    "depth_nado": round(depth_nado, 0),
                    "depth_01": round(depth_01, 0),
                }

                # Store funding history for chart
                now_ts = time.time()
                self._funding_history[pair].append({
                    "timestamp": now_ts,
                    "nado": funding_nado / (365 * 24) if funding_nado else 0,
                    "ex01": funding_01 / (365 * 24) if funding_01 else 0,
                })
                # Keep last 24h of data (one point per 30s = 2880 points)
                cutoff = now_ts - 86400
                self._funding_history[pair] = [
                    p for p in self._funding_history[pair] if p["timestamp"] > cutoff
                ]

                opp = self.risk_manager.evaluate_opportunity(
                    pair, funding_nado, funding_01,
                    spread_nado, spread_01, depth_nado, depth_01,
                )
                new_opportunities.append(opp)

            except Exception as exc:
                logger.warning("Failed to evaluate %s: %s", pair, exc)

        # Check for new viable opportunities
        old_viable = {o["pair"] for o in self.opportunities if o.get("is_viable")}
        new_viable = {o["pair"] for o in new_opportunities if o.get("is_viable")}
        newly_appeared = new_viable - old_viable

        self.opportunities = new_opportunities
        self._daily_opps_seen += len(new_viable)

        # Log rates
        rate_parts = []
        for pair in MONITORED_PAIRS:
            md = self.market_data.get(pair, {})
            fn = md.get("funding_apr_nado", 0)
            f01 = md.get("funding_apr_01", 0)
            rate_parts.append(f"{pair.split('-')[0]}: N={fn:.1f}% 01={f01:.1f}%")
        self._add_log("INFO", f"Funding rates: {', '.join(rate_parts)}")

        # Notify new viable opportunities
        for opp in new_opportunities:
            if opp["pair"] in newly_appeared and opp.get("is_viable"):
                self._add_log("OPRT", f"Nueva oportunidad: {opp['pair']} Net APR {opp['net_apr']:.1f}% (score {opp['score']:.0f})")
                await self.telegram.notify_opportunity(opp)

                # Auto-open if score >= 85 and bot not paused
                if (
                    not self.paused
                    and opp["score"] >= 85
                    and len(self.open_positions) < RISK.MAX_OPEN_POSITIONS
                ):
                    capital = min(
                        RISK.MAX_POSITION_USD,
                        RISK.MAX_POSITION_USD * RISK.POSITION_SIZE_PCT,
                    )
                    if capital >= RISK.MIN_POSITION_USD:
                        self._add_log("OPRT", f"Auto-apertura: {opp['pair']} ${capital:.0f} (score {opp['score']:.0f})")
                        await self.open_position(opp, capital)

    # -----------------------------------------------------------------------
    # Risk check loop — every 5 min
    # -----------------------------------------------------------------------
    async def risk_check_loop(self) -> None:
        """Evaluate risk for all open positions."""
        while self._running:
            try:
                await self._risk_check_cycle()
            except Exception as exc:
                logger.error("Risk check error: %s", exc, exc_info=True)
            await asyncio.sleep(RISK.FUNDING_CHECK_INTERVAL_SECONDS)

    async def _risk_check_cycle(self) -> None:
        for pos in list(self.open_positions):
            if pos.status != "open":
                continue

            try:
                # Get current prices
                long_price = await self._get_current_price(pos.pair, pos.long_protocol)
                short_price = await self._get_current_price(pos.pair, pos.short_protocol)

                # Get current funding rate (hourly %)
                nado_rates = await self.nado.get_funding_rates()
                ex01_rates = self.exchange01.get_funding_rates()
                # The captured funding is from the short side
                if pos.short_protocol == "nado":
                    funding_hourly = nado_rates.get(pos.pair, 0) / (365 * 24)
                else:
                    funding_hourly = ex01_rates.get(pos.pair, 0) / (365 * 24)

                signal = self.risk_manager.evaluate_position(
                    pos, funding_hourly, long_price, short_price
                )

                if signal is None:
                    self._add_log(
                        "RISK",
                        f"{pos.id} OK — PnL: ${pos.net_pnl_usd:.2f} ({pos.net_pnl_pct:.2f}%)",
                    )
                    continue

                # Handle signal
                if signal.should_close:
                    self._add_log("RISK", f"{pos.id}: {signal.reason} — cerrando")
                    await self.close_position(pos, signal.reason)
                    await self.telegram.notify_position_closed(pos, signal.reason)
                elif signal.urgency == "critical":
                    self._add_log("RISK", f"{pos.id}: ALERTA CRITICA — {signal.action_message}")
                    await self.telegram.notify_risk_signal(pos, signal)
                elif signal.urgency == "high":
                    self._add_log("WARN", f"{pos.id}: {signal.action_message}")
                    await self.telegram.notify_risk_signal(pos, signal)

            except Exception as exc:
                logger.error("Risk check for %s failed: %s", pos.id, exc)

    # -----------------------------------------------------------------------
    # Funding accumulation loop — every 1h
    # -----------------------------------------------------------------------
    async def funding_accumulate_loop(self) -> None:
        """Accumulate funding earned/paid for open positions."""
        while self._running:
            await asyncio.sleep(3600)  # Every hour
            try:
                for pos in self.open_positions:
                    if pos.status != "open":
                        continue

                    # Get current funding rate for the short protocol
                    if pos.short_protocol == "nado":
                        rates = await self.nado.get_funding_rates()
                    else:
                        rates = self.exchange01.get_funding_rates()

                    hourly_apr = rates.get(pos.pair, 0)
                    hourly_pct = hourly_apr / (365 * 24) / 100  # Convert APR% to hourly fraction

                    # Funding earned = position size * hourly rate
                    funding_earned = pos.total_capital_usd * hourly_pct
                    pos.funding_collected_usd += funding_earned
                    self._daily_funding += funding_earned

                    self._add_log(
                        "INFO",
                        f"{pos.id}: funding +${funding_earned:.4f} "
                        f"(total: ${pos.funding_collected_usd:.2f})"
                    )

                await self._persist_state()
            except Exception as exc:
                logger.error("Funding accumulation error: %s", exc)

    # -----------------------------------------------------------------------
    # Daily report loop
    # -----------------------------------------------------------------------
    async def daily_report_loop(self) -> None:
        """Send daily summary at 00:00 UTC."""
        while self._running:
            now = datetime.now(timezone.utc)
            # Calculate seconds until next midnight UTC
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now.hour >= 0:
                from datetime import timedelta
                tomorrow += timedelta(days=1)
            seconds_until = (tomorrow - now).total_seconds()
            await asyncio.sleep(max(seconds_until, 60))

            try:
                await self.telegram.notify_daily_summary(
                    positions=self.open_positions,
                    funding_today=self._daily_funding,
                    fees_today=self._daily_fees,
                    opportunities_seen=self._daily_opps_seen,
                    positions_opened=self._daily_opened,
                    positions_closed=self._daily_closed,
                )
                # Reset daily counters
                self._daily_funding = 0.0
                self._daily_fees = 0.0
                self._daily_opps_seen = 0
                self._daily_opened = 0
                self._daily_closed = 0
                self._last_daily_reset = datetime.now(timezone.utc)
            except Exception as exc:
                logger.error("Daily report error: %s", exc)

    # -----------------------------------------------------------------------
    # Position management
    # -----------------------------------------------------------------------
    async def open_position(self, opp: dict, capital_usd: float) -> Optional[Position]:
        """Open a delta-neutral position across both protocols."""
        if len(self.open_positions) >= RISK.MAX_OPEN_POSITIONS:
            self._add_log("WARN", f"Maximo de posiciones alcanzado ({RISK.MAX_OPEN_POSITIONS})")
            await self.telegram.send("No se puede abrir: maximo de posiciones alcanzado.")
            return None

        if capital_usd < RISK.MIN_POSITION_USD:
            self._add_log("WARN", f"Capital ${capital_usd} por debajo del minimo ${RISK.MIN_POSITION_USD}")
            return None

        if capital_usd > RISK.MAX_POSITION_USD:
            capital_usd = RISK.MAX_POSITION_USD

        capital_per_leg = capital_usd / 2

        try:
            long_price = await self._get_current_price(opp["pair"], opp["long_protocol"])
            short_price = await self._get_current_price(opp["pair"], opp["short_protocol"])

            if long_price <= 0 or short_price <= 0:
                self._add_log("ERROR", f"Precio invalido para {opp['pair']}")
                return None

            long_tokens = capital_per_leg / long_price
            short_tokens = capital_per_leg / short_price

            # Opening fees
            fee_open = capital_usd * (NADO_TAKER + EXCHANGE_01_TAKER) / 100

            # Execute both legs concurrently
            long_result, short_result = await asyncio.gather(
                self._place_order(opp["long_protocol"], opp["pair"], "buy", long_tokens, long_price),
                self._place_order(opp["short_protocol"], opp["pair"], "sell", short_tokens, short_price),
            )

            # Calculate estimated liquidation prices
            long_liq = long_price * (1 - 1 / RISK.MAX_LEVERAGE * 0.9)
            short_liq = short_price * (1 + 1 / RISK.MAX_LEVERAGE * 0.9)

            pos = Position(
                id=self._generate_id(opp["pair"]),
                pair=opp["pair"],
                long_protocol=opp["long_protocol"],
                short_protocol=opp["short_protocol"],
                long_size_usd=capital_per_leg,
                short_size_usd=capital_per_leg,
                long_size_tokens=long_tokens,
                short_size_tokens=short_tokens,
                long_entry_price=long_price,
                short_entry_price=short_price,
                long_liq_price=long_liq,
                short_liq_price=short_liq,
                total_capital_usd=capital_usd,
                leverage=RISK.MAX_LEVERAGE,
                entry_funding_apr=opp.get("funding_captured_apr", 0),
                fees_paid_usd=fee_open,
            )

            self.open_positions.append(pos)
            self._daily_opened += 1
            self._daily_fees += fee_open
            await self._persist_state()
            await self.telegram.notify_position_opened(pos)
            self._add_log(
                "OPRT",
                f"Posicion abierta: {pos.id} — {pos.pair} ${capital_usd:.0f} "
                f"(Long {opp['long_protocol'].upper()} / Short {opp['short_protocol'].upper()})"
            )
            return pos

        except Exception as exc:
            logger.error("Failed to open position: %s", exc, exc_info=True)
            self._add_log("ERROR", f"Error abriendo posicion: {exc}")
            return None

    async def close_position(self, pos: Position, reason: str) -> None:
        """Close both legs of a position."""
        pos.status = "closing"
        self._add_log("OPRT", f"Cerrando {pos.id} — motivo: {reason}")

        try:
            long_price = await self._get_current_price(pos.pair, pos.long_protocol)
            short_price = await self._get_current_price(pos.pair, pos.short_protocol)

            await asyncio.gather(
                self._place_order(
                    pos.long_protocol, pos.pair, "sell",
                    pos.long_size_tokens, long_price, reduce_only=True,
                ),
                self._place_order(
                    pos.short_protocol, pos.pair, "buy",
                    pos.short_size_tokens, short_price, reduce_only=True,
                ),
            )
        except Exception as exc:
            logger.error("Error closing position %s: %s", pos.id, exc)

        fee_close = pos.total_capital_usd * (NADO_TAKER + EXCHANGE_01_TAKER) / 100
        pos.fees_paid_usd += fee_close
        pos.status = "closed"
        self._daily_fees += fee_close
        self._daily_closed += 1

        if pos in self.open_positions:
            self.open_positions.remove(pos)
        self.closed_positions.append(pos)
        await self._persist_state()

        self._add_log(
            "OPRT",
            f"Posicion cerrada: {pos.id} — PnL: ${pos.net_pnl_usd:.2f} ({pos.net_pnl_pct:.2f}%)"
        )

    # -----------------------------------------------------------------------
    # Order execution helpers
    # -----------------------------------------------------------------------
    async def _place_order(
        self,
        protocol: str,
        pair: str,
        side: str,
        size_tokens: float,
        price: float,
        reduce_only: bool = False,
    ) -> dict:
        size_usd = size_tokens * price
        if protocol == "nado":
            return await self.nado.place_order(pair, side, size_usd, price, reduce_only)
        else:
            return self.exchange01.place_order(pair, side, size_usd, price, reduce_only)

    async def _get_current_price(self, pair: str, protocol: str) -> float:
        if protocol == "nado":
            price = await self.nado.get_market_price(pair)
        else:
            price = self.exchange01.get_market_price(pair)
        return price

    def _generate_id(self, pair: str) -> str:
        base = pair.split("-")[0]
        count = self._pos_counter.get(base, 0) + 1
        self._pos_counter[base] = count
        return f"{base}-{count:03d}"

    # -----------------------------------------------------------------------
    # Dashboard WebSocket server
    # -----------------------------------------------------------------------
    async def dashboard_ws_server(self) -> None:
        """Run WebSocket server for the dashboard on port 8081."""
        async def handler(ws: websockets.server.WebSocketServerProtocol) -> None:
            self._ws_clients.add(ws)
            logger.info("Dashboard client connected (total: %d)", len(self._ws_clients))
            try:
                async for message in ws:
                    await self._handle_ws_command(message)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self._ws_clients.discard(ws)
                logger.info("Dashboard client disconnected (total: %d)", len(self._ws_clients))

        try:
            server = await websockets.server.serve(
                handler, DASHBOARD.HOST, DASHBOARD.WS_PORT
            )
            logger.info("Dashboard WebSocket server on ws://%s:%d", DASHBOARD.HOST, DASHBOARD.WS_PORT)

            # Broadcast state every 5 seconds
            while self._running:
                await self._broadcast_state()
                await asyncio.sleep(5)

            server.close()
            await server.wait_closed()
        except Exception as exc:
            logger.error("WebSocket server error: %s", exc)

    async def _broadcast_state(self) -> None:
        """Send current state to all connected dashboard clients."""
        if not self._ws_clients:
            return

        state = self._build_state_payload()
        data = json.dumps(state)

        disconnected = set()
        for ws in self._ws_clients:
            try:
                await ws.send(data)
            except Exception:
                disconnected.add(ws)

        self._ws_clients -= disconnected

    def _build_state_payload(self) -> dict:
        total_capital = sum(p.total_capital_usd for p in self.open_positions)
        total_funding = sum(p.funding_collected_usd for p in self.open_positions)
        total_fees = sum(p.fees_paid_usd for p in self.open_positions)
        net_pnl = total_funding - total_fees

        return {
            "type": "state",
            "timestamp": time.time(),
            "system": {
                "status": "running" if self._running else "stopped",
                "dry_run": RISK.DRY_RUN,
                "paused": self.paused,
                "nado_connected": self.nado.is_connected,
                "exchange01_connected": self.exchange01.is_connected,
                "exchange01_mock": self.exchange01.mock_mode,
            },
            "opportunities": self.opportunities,
            "positions": [p.to_dict() for p in self.open_positions],
            "closed_positions": [p.to_dict() for p in self.closed_positions[-20:]],
            "market_data": self.market_data,
            "funding_history": {
                pair: hist[-200:]  # Last ~200 data points for chart
                for pair, hist in self._funding_history.items()
            },
            "portfolio": {
                "total_capital_deployed": round(total_capital, 2),
                "funding_collected_usd": round(total_funding, 4),
                "fees_paid_usd": round(total_fees, 4),
                "net_pnl_usd": round(net_pnl, 4),
                "net_pnl_pct": round(net_pnl / total_capital * 100, 4) if total_capital > 0 else 0,
            },
            "recent_logs": self.recent_logs[-50:],
            "risk_config": {
                "max_position_usd": RISK.MAX_POSITION_USD,
                "min_position_usd": RISK.MIN_POSITION_USD,
                "max_leverage": RISK.MAX_LEVERAGE,
                "max_open_positions": RISK.MAX_OPEN_POSITIONS,
                "min_net_apr_pct": RISK.MIN_NET_APR_PCT,
                "max_spread_pct": RISK.MAX_SPREAD_PCT,
                "stop_loss_pnl_pct": RISK.STOP_LOSS_PNL_PCT,
                "liq_buffer_pct": RISK.LIQUIDATION_BUFFER_PCT,
            },
        }

    async def _handle_ws_command(self, raw: str) -> None:
        """Handle commands from the dashboard via WebSocket."""
        try:
            cmd = json.loads(raw)
        except json.JSONDecodeError:
            return

        action = cmd.get("action", "")
        logger.info("Dashboard command: %s", action)

        if action == "open":
            pair = cmd.get("pair", "")
            capital = float(cmd.get("capital", 0))
            if pair in MONITORED_PAIRS and capital >= RISK.MIN_POSITION_USD:
                # Find the best opportunity for this pair
                for opp in self.opportunities:
                    if opp["pair"] == pair:
                        await self.open_position(opp, capital)
                        break

        elif action == "close":
            pos_id = cmd.get("position_id", "")
            for pos in self.open_positions:
                if pos.id == pos_id:
                    await self.close_position(pos, "MANUAL")
                    await self.telegram.notify_position_closed(pos, "MANUAL")
                    break

        elif action == "pause":
            self.paused = True
            self._add_log("INFO", "Bot pausado desde dashboard")

        elif action == "resume":
            self.paused = False
            self._add_log("INFO", "Bot reanudado desde dashboard")

        elif action == "set_risk":
            param = cmd.get("param", "")
            value = cmd.get("value")
            if param and value is not None:
                attr = param.upper()
                if hasattr(RISK, attr):
                    setattr(RISK, attr, float(value))
                    self._add_log("INFO", f"Riesgo actualizado: {attr} = {value}")

        elif action == "refresh":
            await self._monitor_cycle()

        elif action == "request_real_mode":
            await self.telegram.send(
                "<b>Solicitud de modo REAL desde dashboard.</b>\n"
                "Usa /dryrun off en Telegram para confirmar."
            )

    # -----------------------------------------------------------------------
    # Telegram command callbacks
    # -----------------------------------------------------------------------
    async def _tg_open_position(self, pair: str, capital: float) -> None:
        for opp in self.opportunities:
            if opp["pair"] == pair:
                await self.open_position(opp, capital)
                return
        # If no current opportunity, create a basic one
        opp = {
            "pair": pair,
            "long_protocol": "01",
            "short_protocol": "nado",
            "funding_captured_apr": 0,
            "net_apr": 0,
            "score": 0,
        }
        await self.open_position(opp, capital)

    async def _tg_close_position(self, pos_id: str) -> None:
        for pos in self.open_positions:
            if pos.id == pos_id:
                await self.close_position(pos, "MANUAL")
                await self.telegram.notify_position_closed(pos, "MANUAL")
                return
        await self.telegram.send(f"Posicion {pos_id} no encontrada.")

    async def _tg_close_all(self) -> None:
        for pos in list(self.open_positions):
            await self.close_position(pos, "CIERRE_TOTAL")
            await self.telegram.notify_position_closed(pos, "CIERRE_TOTAL")
        await self.telegram.send("Todas las posiciones cerradas.")

    async def _tg_pause(self) -> None:
        self.paused = True
        self._add_log("INFO", "Bot pausado via Telegram")

    async def _tg_resume(self) -> None:
        self.paused = False
        self._add_log("INFO", "Bot reanudado via Telegram")

    async def _tg_set_risk(self, param: str, value: float) -> None:
        self._add_log("INFO", f"Riesgo actualizado via Telegram: {param} = {value}")

    async def _tg_set_dryrun(self, enabled: bool) -> None:
        RISK.DRY_RUN = enabled
        mode = "SIMULACION" if enabled else "REAL"
        self._add_log("INFO", f"Modo cambiado a {mode} via Telegram")
        await self._persist_state()

    # -----------------------------------------------------------------------
    # Status helper
    # -----------------------------------------------------------------------
    def _get_status_dict(self) -> dict:
        total_capital = sum(p.total_capital_usd for p in self.open_positions)
        net_pnl = sum(p.net_pnl_usd for p in self.open_positions)
        return {
            "paused": self.paused,
            "nado_connected": self.nado.is_connected,
            "exchange01_connected": self.exchange01.is_connected,
            "open_positions": len(self.open_positions),
            "total_capital": total_capital,
            "net_pnl": net_pnl,
        }

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------
    async def _persist_state(self) -> None:
        """Save positions and state to disk."""
        try:
            # Positions
            positions_data = [p.to_dict() for p in self.open_positions]
            POSITIONS_FILE.write_text(json.dumps(positions_data, indent=2))

            # History
            history_data = [p.to_dict() for p in self.closed_positions[-100:]]
            HISTORY_FILE.write_text(json.dumps(history_data, indent=2))

            # State
            state_data = {
                "paused": self.paused,
                "dry_run": RISK.DRY_RUN,
                "pos_counter": self._pos_counter,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            STATE_FILE.write_text(json.dumps(state_data, indent=2))

        except Exception as exc:
            logger.error("Failed to persist state: %s", exc)

    def _load_state(self) -> None:
        """Load positions and state from disk."""
        # Load positions
        if POSITIONS_FILE.exists():
            try:
                data = json.loads(POSITIONS_FILE.read_text())
                self.open_positions = [Position.from_dict(d) for d in data]
                logger.info("Loaded %d open positions", len(self.open_positions))
            except Exception as exc:
                logger.warning("Failed to load positions: %s", exc)

        # Load history
        if HISTORY_FILE.exists():
            try:
                data = json.loads(HISTORY_FILE.read_text())
                self.closed_positions = [Position.from_dict(d) for d in data]
                logger.info("Loaded %d closed positions", len(self.closed_positions))
            except Exception as exc:
                logger.warning("Failed to load history: %s", exc)

        # Load state
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.paused = data.get("paused", False)
                self._pos_counter = data.get("pos_counter", {})
                saved_dry = data.get("dry_run")
                if saved_dry is not None and not RISK.DRY_RUN:
                    # Only restore dry_run if env didn't override to real
                    pass
                logger.info("State loaded (paused=%s)", self.paused)
            except Exception as exc:
                logger.warning("Failed to load state: %s", exc)

    # -----------------------------------------------------------------------
    # Logging helper
    # -----------------------------------------------------------------------
    def _add_log(self, level: str, message: str) -> None:
        now = datetime.now(timezone.utc)
        entry = {
            "timestamp": now.isoformat(),
            "time_str": now.strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 100:
            self.recent_logs = self.recent_logs[-100:]

        log_level = {
            "INFO": logging.INFO,
            "OPRT": logging.INFO,
            "RISK": logging.INFO,
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR,
        }.get(level, logging.INFO)
        logger.log(log_level, "[%s] %s", level, message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    bot = DeltaNeutralBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Shutdown by user (Ctrl+C)")


if __name__ == "__main__":
    main()
