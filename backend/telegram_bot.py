"""
Telegram bot for the Delta-Neutral Arbitrage system.
Provides alerts, control commands, and confirmation workflows.
Uses python-telegram-bot v20+ (async).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import RISK, TELEGRAM, MONITORED_PAIRS
from risk_manager import Position, RiskSignal

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for alerts and remote control of the arbitrage system."""

    def __init__(self) -> None:
        self.token: str = TELEGRAM.BOT_TOKEN
        self.chat_id: str = TELEGRAM.CHAT_ID
        self.app: Optional[Application] = None
        self._bot_ref: Optional[Any] = None

        # Callbacks set by the main bot engine
        self.on_open_position: Optional[Callable[..., Coroutine]] = None
        self.on_close_position: Optional[Callable[..., Coroutine]] = None
        self.on_close_all: Optional[Callable[..., Coroutine]] = None
        self.on_pause: Optional[Callable[..., Coroutine]] = None
        self.on_resume: Optional[Callable[..., Coroutine]] = None
        self.on_set_risk: Optional[Callable[..., Coroutine]] = None
        self.on_set_dryrun: Optional[Callable[..., Coroutine]] = None

        # References to bot state (set by main bot)
        self.get_status: Optional[Callable] = None
        self.get_opportunities: Optional[Callable] = None
        self.get_positions: Optional[Callable] = None

    def _authorized(self, update: Update) -> bool:
        """Check that the message comes from the authorized chat."""
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        if chat_id != self.chat_id:
            logger.warning("Unauthorized access attempt from chat_id=%s", chat_id)
            return False
        return True

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------
    async def start(self) -> None:
        """Start the Telegram bot (non-blocking)."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram token/chat_id not configured — bot disabled")
            return

        self.app = Application.builder().token(self.token).build()
        self._register_handlers()
        await self.app.initialize()
        await self.app.start()
        if self.app.updater:
            await self.app.updater.start_polling(drop_pending_updates=True)
        self._bot_ref = self.app.bot
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self.app:
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            if self.app.running:
                await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram bot stopped")

    def _register_handlers(self) -> None:
        if not self.app:
            return
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("opportunities", self._cmd_opportunities))
        self.app.add_handler(CommandHandler("positions", self._cmd_positions))
        self.app.add_handler(CommandHandler("open", self._cmd_open))
        self.app.add_handler(CommandHandler("close", self._cmd_close))
        self.app.add_handler(CommandHandler("closeall", self._cmd_closeall))
        self.app.add_handler(CommandHandler("pause", self._cmd_pause))
        self.app.add_handler(CommandHandler("resume", self._cmd_resume))
        self.app.add_handler(CommandHandler("risk", self._cmd_risk))
        self.app.add_handler(CommandHandler("setrisk", self._cmd_setrisk))
        self.app.add_handler(CommandHandler("dryrun", self._cmd_dryrun))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))

    # -----------------------------------------------------------------------
    # Send message helpers
    # -----------------------------------------------------------------------
    async def send(self, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        """Send a message to the configured chat."""
        if not self._bot_ref:
            logger.debug("Telegram bot not ready — message dropped: %s", text[:80])
            return
        try:
            await self._bot_ref.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except Exception as exc:
            logger.error("Failed to send Telegram message: %s", exc)

    def _dry_prefix(self) -> str:
        return "[SIMULACION] " if RISK.DRY_RUN else ""

    # -----------------------------------------------------------------------
    # Notification methods (called by the main bot engine)
    # -----------------------------------------------------------------------
    async def notify_opportunity(self, opp: dict) -> None:
        """Send opportunity alert with action buttons."""
        prefix = self._dry_prefix()
        capital = min(RISK.MAX_POSITION_USD, 450)
        text = (
            f"{prefix}<b>OPORTUNIDAD DETECTADA</b>\n"
            f"{'=' * 32}\n"
            f"Par: <b>{opp['pair']}</b>  |  Score: <b>{opp['score']:.0f}/100</b>\n"
            f"Long: {opp['long_protocol'].upper()}  |  Short: {opp['short_protocol'].upper()}\n\n"
            f"Funding capturado: {opp['hourly_funding_pct']:.4f}%/h ({opp['funding_captured_apr']:.1f}% APR)\n"
            f"Fees round-trip: {opp['total_fee_pct']:.2f}%\n"
            f"Spread total: {opp['total_spread_pct']:.4f}%\n"
            f"Net APR estimado: <b>{opp['net_apr']:.1f}%</b>\n\n"
            f"Capital sugerido: <b>${capital}</b>\n"
            f"Break-even: ~{opp['breakeven_hours']:.0f} horas\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"ABRIR ${capital}", callback_data=f"open_{opp['pair']}_{capital}"),
                InlineKeyboardButton("REVISAR", callback_data=f"review_{opp['pair']}"),
                InlineKeyboardButton("IGNORAR", callback_data="ignore"),
            ]
        ])
        await self.send(text, reply_markup=keyboard)

    async def notify_position_opened(self, pos: Position) -> None:
        """Notify that a position was opened."""
        prefix = self._dry_prefix()
        daily_est = pos.total_capital_usd * (pos.entry_funding_apr / 100) / 365

        text = (
            f"{prefix}<b>POSICION ABIERTA</b>\n"
            f"{'=' * 32}\n"
            f"ID: <b>{pos.id}</b>  |  Par: {pos.pair}\n"
            f"Long {pos.long_protocol.upper()}: ${pos.long_size_usd:.2f} @ ${pos.long_entry_price:.2f}"
            f"  ({pos.long_size_tokens:.4f} tokens)\n"
            f"Short {pos.short_protocol.upper()}: ${pos.short_size_usd:.2f} @ ${pos.short_entry_price:.2f}"
            f"  ({pos.short_size_tokens:.4f} tokens)\n"
            f"Capital total: <b>${pos.total_capital_usd:.2f}</b>\n\n"
            f"Net APR esperado: {pos.entry_funding_apr:.1f}%\n"
            f"Funding diario estimado: +${daily_est:.2f}\n"
            f"Fees pagadas apertura: -${pos.fees_paid_usd:.2f}\n\n"
            f"Liq. Long: ${pos.long_liq_price:.2f}\n"
            f"Liq. Short: ${pos.short_liq_price:.2f}\n"
        )
        await self.send(text)

    async def notify_position_closed(self, pos: Position, reason: str) -> None:
        """Notify that a position was closed."""
        prefix = self._dry_prefix()

        if reason == "STOP_LOSS":
            emoji = "STOP LOSS ACTIVADO"
        elif reason == "FUNDING_INVERTIDO":
            emoji = "POSICION CERRADA"
        else:
            emoji = "POSICION CERRADA"

        text = (
            f"{prefix}<b>{emoji} — {pos.id}</b>\n"
            f"{'=' * 32}\n"
            f"Motivo: {reason}\n"
            f"Duracion: {pos.age_hours:.1f} horas\n\n"
            f"Funding cobrado: +${pos.funding_collected_usd:.2f}\n"
            f"Fees pagadas (apertura + cierre): -${pos.fees_paid_usd:.2f}\n"
            f"Net PnL: {'+'if pos.net_pnl_usd >= 0 else ''}${pos.net_pnl_usd:.2f}"
            f" ({'+' if pos.net_pnl_pct >= 0 else ''}{pos.net_pnl_pct:.2f}%)\n"
            f"APR real obtenido: {pos.realized_apr:.1f}%\n"
        )
        await self.send(text)

    async def notify_risk_signal(self, pos: Position, signal: RiskSignal) -> None:
        """Send risk alert for a position."""
        prefix = self._dry_prefix()

        if signal.reason == "ALERTA_LIQ":
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("CERRAR AHORA", callback_data=f"close_{pos.id}"),
                    InlineKeyboardButton("IGNORAR (riesgo)", callback_data="ignore"),
                ]
            ])
            text = (
                f"{prefix}<b>ALERTA CRITICA — LIQUIDACION CERCANA</b>\n"
                f"{'=' * 32}\n"
                f"Posicion: {pos.id}\n"
                f"Distancia long: {signal.details.get('long_dist_pct', 0):.1f}%\n"
                f"Distancia short: {signal.details.get('short_dist_pct', 0):.1f}%\n"
                f"ACCION REQUERIDA: Anadir margen o cerrar manualmente AHORA\n"
            )
            await self.send(text, reply_markup=keyboard)

        elif signal.reason == "FUNDING_NEGATIVO_ADVERTENCIA":
            text = (
                f"{prefix}<b>FUNDING NEGATIVO — {pos.id}</b>\n"
                f"{'=' * 32}\n"
                f"Rate actual: {signal.details.get('rate', 0):.4f}%/h\n"
                f"Confirmacion: {signal.details.get('checks', 0)}/{signal.details.get('needed', 3)}"
                f" (esperando mas para cerrar)\n\n"
                f"PnL actual: {'+'if pos.net_pnl_usd >= 0 else ''}${pos.net_pnl_usd:.2f}"
                f" ({'+' if pos.net_pnl_pct >= 0 else ''}{pos.net_pnl_pct:.2f}%)\n"
                f"Funding cobrado: +${pos.funding_collected_usd:.2f}  |  Fees: -${pos.fees_paid_usd:.2f}\n"
            )
            await self.send(text)

        elif signal.should_close:
            text = (
                f"{prefix}<b>{signal.reason} — {pos.id}</b>\n"
                f"{'=' * 32}\n"
                f"{signal.action_message}\n"
            )
            await self.send(text)

    async def notify_daily_summary(
        self,
        positions: list,
        funding_today: float,
        fees_today: float,
        opportunities_seen: int,
        positions_opened: int,
        positions_closed: int,
    ) -> None:
        """Send daily summary report at 00:00 UTC."""
        prefix = self._dry_prefix()
        total_capital = sum(p.total_capital_usd for p in positions)
        net_pnl = funding_today - fees_today
        net_pct = (net_pnl / total_capital * 100) if total_capital > 0 else 0
        mode = "SIMULACION" if RISK.DRY_RUN else "REAL"

        text = (
            f"{prefix}<b>RESUMEN DIARIO</b>\n"
            f"{'=' * 32}\n"
            f"Posiciones activas: {len(positions)}  |  Capital: ${total_capital:.2f}\n"
            f"Funding cobrado hoy: +${funding_today:.2f}\n"
            f"Fees hoy: -${fees_today:.2f}\n"
            f"Net PnL hoy: {'+'if net_pnl >= 0 else ''}${net_pnl:.2f}"
            f" ({'+' if net_pct >= 0 else ''}{net_pct:.3f}%)\n\n"
            f"Sistema: OPERATIVO  |  Modo: {mode}\n"
            f"Oportunidades vistas hoy: {opportunities_seen}\n"
            f"Posiciones abiertas hoy: {positions_opened}  |  Cerradas: {positions_closed}\n"
        )
        await self.send(text)

    async def notify_system_start(self, nado_ok: bool, ex01_ok: bool) -> None:
        """Notify that the bot has started."""
        mode = "SIMULACION" if RISK.DRY_RUN else "REAL"
        nado_s = "OK" if nado_ok else "FAIL"
        ex01_s = "OK" if ex01_ok else "MOCK"
        text = (
            f"<b>Bot arrancado</b>\n"
            f"Modo: {mode}\n"
            f"Nado: {nado_s}  |  01 Exchange: {ex01_s}\n"
            f"Pares: {', '.join(MONITORED_PAIRS)}\n"
            f"Capital max/posicion: ${RISK.MAX_POSITION_USD}\n"
            f"Min Net APR: {RISK.MIN_NET_APR_PCT}%\n"
        )
        await self.send(text)

    # -----------------------------------------------------------------------
    # Command handlers
    # -----------------------------------------------------------------------
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        await update.message.reply_text(
            "Delta-Neutral Arbitrage Bot activo.\nUsa /help para ver comandos."
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        text = (
            "<b>Comandos disponibles:</b>\n\n"
            "/status — Estado del sistema y posiciones\n"
            "/opportunities — Oportunidades ordenadas por Net APR\n"
            "/positions — Detalle de posiciones abiertas\n"
            "/open &lt;par&gt; &lt;capital&gt; — Abrir posicion manual\n"
            "/close &lt;id&gt; — Cerrar posicion\n"
            "/closeall — Cerrar todas las posiciones\n"
            "/pause — Pausar apertura de nuevas posiciones\n"
            "/resume — Reanudar operacion\n"
            "/risk — Ver parametros de riesgo\n"
            "/setrisk &lt;param&gt; &lt;valor&gt; — Modificar parametro\n"
            "/dryrun on|off — Cambiar modo simulacion/real\n"
            "/help — Esta ayuda\n"
        )
        await update.message.reply_html(text)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        if self.get_status:
            status = self.get_status()
        else:
            status = {"mode": "UNKNOWN", "positions": 0, "pnl": 0}

        mode = "SIMULACION" if RISK.DRY_RUN else "REAL"
        paused = status.get("paused", False)
        text = (
            f"<b>Estado del Sistema</b>\n"
            f"{'=' * 32}\n"
            f"Modo: {mode}\n"
            f"Pausado: {'SI' if paused else 'NO'}\n"
            f"Nado: {'OK' if status.get('nado_connected', False) else 'DESCONECTADO'}\n"
            f"01 Exchange: {'OK' if status.get('exchange01_connected', False) else 'MOCK'}\n\n"
            f"Posiciones abiertas: {status.get('open_positions', 0)}\n"
            f"Capital desplegado: ${status.get('total_capital', 0):.2f}\n"
            f"Net PnL: ${status.get('net_pnl', 0):.2f}\n"
        )
        await update.message.reply_html(text)

    async def _cmd_opportunities(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        if not self.get_opportunities:
            await update.message.reply_text("Sin datos de oportunidades")
            return

        opps = self.get_opportunities()
        if not opps:
            await update.message.reply_text("No hay oportunidades detectadas")
            return

        sorted_opps = sorted(opps, key=lambda o: o.get("net_apr", 0), reverse=True)
        lines = ["<b>Oportunidades</b>\n"]
        for o in sorted_opps[:10]:
            viable = "V" if o.get("is_viable") else "X"
            lines.append(
                f"[{viable}] {o['pair']} | Score: {o['score']:.0f} | "
                f"Net APR: {o['net_apr']:.1f}% | BrkEven: {o['breakeven_hours']:.0f}h"
            )
            if not o.get("is_viable") and o.get("rejection_reason"):
                lines.append(f"    Motivo: {o['rejection_reason']}")
        await update.message.reply_html("\n".join(lines))

    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        if not self.get_positions:
            await update.message.reply_text("Sin datos de posiciones")
            return

        positions = self.get_positions()
        if not positions:
            await update.message.reply_text("No hay posiciones abiertas")
            return

        lines = ["<b>Posiciones Abiertas</b>\n"]
        for p in positions:
            if isinstance(p, Position):
                lines.append(
                    f"<b>{p.id}</b> | {p.pair}\n"
                    f"  Long {p.long_protocol.upper()}: ${p.long_size_usd:.2f}\n"
                    f"  Short {p.short_protocol.upper()}: ${p.short_size_usd:.2f}\n"
                    f"  Capital: ${p.total_capital_usd:.2f} | Edad: {p.age_hours:.1f}h\n"
                    f"  PnL: ${p.net_pnl_usd:.2f} ({p.net_pnl_pct:.2f}%)\n"
                    f"  APR real: {p.realized_apr:.1f}%\n"
                )
            else:
                lines.append(f"  {p}")
        await update.message.reply_html("\n".join(lines))

    async def _cmd_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text("Uso: /open <par> <capital>\nEj: /open ETH-PERP 400")
            return

        pair = args[0].upper()
        try:
            capital = float(args[1])
        except ValueError:
            await update.message.reply_text("Capital debe ser un numero")
            return

        if pair not in MONITORED_PAIRS:
            await update.message.reply_text(f"Par no soportado. Disponibles: {', '.join(MONITORED_PAIRS)}")
            return
        if capital < RISK.MIN_POSITION_USD:
            await update.message.reply_text(f"Capital minimo: ${RISK.MIN_POSITION_USD}")
            return
        if capital > RISK.MAX_POSITION_USD:
            await update.message.reply_text(f"Capital maximo: ${RISK.MAX_POSITION_USD}")
            return

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"CONFIRMAR: Abrir {pair} ${capital}",
                    callback_data=f"confirm_open_{pair}_{capital}",
                ),
                InlineKeyboardButton("CANCELAR", callback_data="ignore"),
            ]
        ])
        await update.message.reply_html(
            f"<b>Confirmar apertura:</b>\n{pair} con ${capital}",
            reply_markup=keyboard,
        )

    async def _cmd_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        args = context.args or []
        if len(args) < 1:
            await update.message.reply_text("Uso: /close <id>\nEj: /close ETH-001")
            return

        pos_id = args[0]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"CONFIRMAR: Cerrar {pos_id}", callback_data=f"confirm_close_{pos_id}"),
                InlineKeyboardButton("CANCELAR", callback_data="ignore"),
            ]
        ])
        await update.message.reply_html(
            f"<b>Confirmar cierre:</b>\nPosicion {pos_id}",
            reply_markup=keyboard,
        )

    async def _cmd_closeall(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("CONFIRMAR: Cerrar TODAS", callback_data="confirm_closeall"),
                InlineKeyboardButton("CANCELAR", callback_data="ignore"),
            ]
        ])
        await update.message.reply_html(
            "<b>Cerrar TODAS las posiciones?</b>\nEsta accion no se puede deshacer.",
            reply_markup=keyboard,
        )

    async def _cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        if self.on_pause:
            await self.on_pause()
        await update.message.reply_text("Bot pausado. No se abriran nuevas posiciones.\nUsa /resume para reanudar.")

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        if self.on_resume:
            await self.on_resume()
        await update.message.reply_text("Bot reanudado. Se evaluaran nuevas oportunidades.")

    async def _cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        text = (
            "<b>Parametros de Riesgo</b>\n"
            f"{'=' * 32}\n"
            f"MAX_POSITION_USD: ${RISK.MAX_POSITION_USD}\n"
            f"MIN_POSITION_USD: ${RISK.MIN_POSITION_USD}\n"
            f"MAX_LEVERAGE: {RISK.MAX_LEVERAGE}x\n"
            f"MAX_OPEN_POSITIONS: {RISK.MAX_OPEN_POSITIONS}\n"
            f"MIN_NET_APR_PCT: {RISK.MIN_NET_APR_PCT}%\n"
            f"MAX_SPREAD_PCT: {RISK.MAX_SPREAD_PCT}%\n"
            f"STOP_LOSS_PNL_PCT: {RISK.STOP_LOSS_PNL_PCT}%\n"
            f"LIQ_BUFFER_PCT: {RISK.LIQUIDATION_BUFFER_PCT}%\n"
            f"MAX_BREAKEVEN_HOURS: {RISK.MAX_BREAKEVEN_HOURS}h\n"
            f"MAX_AGE_HOURS: {RISK.MAX_POSITION_AGE_HOURS}h\n"
            f"DRY_RUN: {RISK.DRY_RUN}\n"
        )
        await update.message.reply_html(text)

    async def _cmd_setrisk(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Uso: /setrisk <parametro> <valor>\n"
                "Ej: /setrisk min_net_apr_pct 40\n\n"
                "Parametros: max_position_usd, min_position_usd, min_net_apr_pct, "
                "max_spread_pct, stop_loss_pnl_pct, liq_buffer_pct, max_breakeven_hours"
            )
            return

        param = args[0].lower()
        try:
            value = float(args[1])
        except ValueError:
            await update.message.reply_text("Valor debe ser numerico")
            return

        param_map = {
            "max_position_usd": "MAX_POSITION_USD",
            "min_position_usd": "MIN_POSITION_USD",
            "min_net_apr_pct": "MIN_NET_APR_PCT",
            "max_spread_pct": "MAX_SPREAD_PCT",
            "stop_loss_pnl_pct": "STOP_LOSS_PNL_PCT",
            "liq_buffer_pct": "LIQUIDATION_BUFFER_PCT",
            "max_breakeven_hours": "MAX_BREAKEVEN_HOURS",
            "max_leverage": "MAX_LEVERAGE",
        }

        attr = param_map.get(param)
        if not attr:
            await update.message.reply_text(f"Parametro desconocido: {param}")
            return

        old_val = getattr(RISK, attr)
        setattr(RISK, attr, value)
        if self.on_set_risk:
            await self.on_set_risk(attr, value)

        await update.message.reply_html(
            f"<b>Parametro actualizado:</b>\n{attr}: {old_val} -> {value}"
        )

    async def _cmd_dryrun(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            return
        args = context.args or []
        if not args or args[0].lower() not in ("on", "off"):
            await update.message.reply_text("Uso: /dryrun on|off")
            return

        if args[0].lower() == "off":
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "CONFIRMAR: MODO REAL",
                        callback_data="confirm_dryrun_off",
                    ),
                    InlineKeyboardButton("CANCELAR", callback_data="ignore"),
                ]
            ])
            await update.message.reply_html(
                "<b>ATENCION: Activar modo REAL?</b>\n"
                "Las ordenes se ejecutaran en los exchanges reales.\n"
                "Asegurate de tener fondos y de haber verificado el sistema.",
                reply_markup=keyboard,
            )
        else:
            RISK.DRY_RUN = True
            if self.on_set_dryrun:
                await self.on_set_dryrun(True)
            await update.message.reply_text("Modo SIMULACION activado.")

    # -----------------------------------------------------------------------
    # Callback handler (inline buttons)
    # -----------------------------------------------------------------------
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()

        if not self._authorized(update):
            return

        data = query.data or ""

        if data == "ignore":
            await query.edit_message_reply_markup(reply_markup=None)
            return

        if data.startswith("open_"):
            # open_{pair}_{capital}
            parts = data.split("_", 2)
            if len(parts) >= 3:
                pair = parts[1]
                capital = float(parts[2])
                await query.edit_message_reply_markup(reply_markup=None)
                if self.on_open_position:
                    await self.on_open_position(pair, capital)
                else:
                    await self.send(f"Abriendo {pair} con ${capital}...")

        elif data.startswith("confirm_open_"):
            parts = data.replace("confirm_open_", "").rsplit("_", 1)
            if len(parts) >= 2:
                pair = parts[0]
                capital = float(parts[1])
                await query.edit_message_reply_markup(reply_markup=None)
                if self.on_open_position:
                    await self.on_open_position(pair, capital)
                else:
                    await self.send(f"Abriendo {pair} con ${capital}...")

        elif data.startswith("close_") or data.startswith("confirm_close_"):
            pos_id = data.replace("confirm_close_", "").replace("close_", "")
            await query.edit_message_reply_markup(reply_markup=None)
            if self.on_close_position:
                await self.on_close_position(pos_id)
            else:
                await self.send(f"Cerrando posicion {pos_id}...")

        elif data == "confirm_closeall":
            await query.edit_message_reply_markup(reply_markup=None)
            if self.on_close_all:
                await self.on_close_all()
            else:
                await self.send("Cerrando todas las posiciones...")

        elif data == "confirm_dryrun_off":
            RISK.DRY_RUN = False
            await query.edit_message_reply_markup(reply_markup=None)
            if self.on_set_dryrun:
                await self.on_set_dryrun(False)
            await self.send("<b>MODO REAL ACTIVADO.</b>\nLas ordenes se ejecutaran en los exchanges.")

        elif data.startswith("review_"):
            pair = data.replace("review_", "")
            await query.edit_message_reply_markup(reply_markup=None)
            await self.send(f"Revisa la oportunidad de {pair} en el dashboard web.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Telegram bot module loaded. Run via bot.py for full functionality.")
