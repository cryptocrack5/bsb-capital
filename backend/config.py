"""
Configuration module for the Delta-Neutral Arbitrage Bot.
All values are read from environment variables with sensible defaults
calibrated for capital < $1,000 per operation.
"""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, str(default)).lower()
    return val in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Monitored pairs
# ---------------------------------------------------------------------------
MONITORED_PAIRS: List[str] = ["BTC-PERP", "ETH-PERP", "SOL-PERP"]


# ---------------------------------------------------------------------------
# Risk configuration — calibrated for < $1,000
# ---------------------------------------------------------------------------
@dataclass
class RiskConfig:
    """Risk parameters tuned for small-capital operation (< $1,000)."""

    # Capital limits
    MAX_POSITION_USD: float = _env_float("MAX_POSITION_USD", 500.0)
    MIN_POSITION_USD: float = _env_float("MIN_POSITION_USD", 150.0)
    POSITION_SIZE_PCT: float = _env_float("POSITION_SIZE_PCT", 0.40)
    MAX_OPEN_POSITIONS: int = _env_int("MAX_OPEN_POSITIONS", 2)
    MAX_LEVERAGE: float = _env_float("MAX_LEVERAGE", 2.0)

    # Opportunity thresholds — stricter for small capital
    MIN_NET_APR_PCT: float = _env_float("MIN_NET_APR_PCT", 35.0)
    MAX_SPREAD_PCT: float = _env_float("MAX_SPREAD_PCT", 0.06)
    MIN_OPPORTUNITY_SCORE: float = _env_float("MIN_OPPORTUNITY_SCORE", 70.0)
    MIN_FUNDING_HOURLY_PCT: float = _env_float("MIN_FUNDING_HOURLY_PCT", 0.004)

    # RULE 1: Stop if funding inverts sign
    STOP_IF_FUNDING_INVERTS: bool = _env_bool("STOP_IF_FUNDING_INVERTS", True)
    FUNDING_INVERSION_CHECKS: int = _env_int("FUNDING_INVERSION_CHECKS", 3)

    # RULE 2: Stop loss by PnL
    STOP_LOSS_PNL_PCT: float = _env_float("STOP_LOSS_PCT", 3.0)

    # RULE 3: Max simultaneous positions -> MAX_OPEN_POSITIONS

    # Liquidation buffer — conservative
    LIQUIDATION_BUFFER_PCT: float = _env_float("LIQ_BUFFER_PCT", 35.0)

    # Operational
    MONITOR_INTERVAL_SECONDS: int = _env_int("MONITOR_INTERVAL", 30)
    FUNDING_CHECK_INTERVAL_SECONDS: int = _env_int("FUNDING_CHECK_INTERVAL", 300)
    DRY_RUN: bool = _env_bool("DRY_RUN", True)
    USE_MOCK_DATA: bool = _env_bool("USE_MOCK_DATA", False)
    MAX_POSITION_AGE_HOURS: float = _env_float("MAX_AGE_HOURS", 120.0)

    # Break-even
    MAX_BREAKEVEN_HOURS: float = _env_float("MAX_BREAKEVEN_HOURS", 96.0)


# ---------------------------------------------------------------------------
# Nado Finance configuration (Ink L2)
# ---------------------------------------------------------------------------
@dataclass
class NadoConfig:
    """Connection and fee settings for Nado Finance on Ink L2."""

    GATEWAY_REST_V1: str = "https://gateway.prod.nado.xyz/v1"
    GATEWAY_REST_V2: str = "https://gateway.prod.nado.xyz/v2"
    GATEWAY_WS: str = "wss://gateway.prod.nado.xyz/v1/ws"
    SUBSCRIBE_WS: str = "wss://gateway.prod.nado.xyz/v1/subscribe"
    ARCHIVE_V1: str = "https://archive.prod.nado.xyz/v1"
    ARCHIVE_V2: str = "https://archive.prod.nado.xyz/v2"

    PRIVATE_KEY: str = field(default_factory=lambda: _env("NADO_PRIVATE_KEY", ""))

    # Fees
    MAKER_FEE_PCT: float = -0.01  # rebate
    TAKER_FEE_PCT: float = 0.04


# ---------------------------------------------------------------------------
# 01 Exchange configuration (Solana, local API)
# ---------------------------------------------------------------------------
@dataclass
class Exchange01Config:
    """Connection and fee settings for 01 Exchange local REST API."""

    BASE_URL: str = field(default_factory=lambda: _env("EXCHANGE_01_URL", "http://localhost:3000"))
    PRIVATE_KEY: str = field(default_factory=lambda: _env("EXCHANGE_01_PRIVATE_KEY", ""))

    # Fees
    MAKER_FEE_PCT: float = 0.02
    TAKER_FEE_PCT: float = 0.05


# ---------------------------------------------------------------------------
# Telegram configuration
# ---------------------------------------------------------------------------
@dataclass
class TelegramConfig:
    """Telegram bot settings."""

    BOT_TOKEN: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", ""))
    CHAT_ID: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID", ""))

    SEND_OPPORTUNITY_ALERTS: bool = True
    SEND_POSITION_ALERTS: bool = True
    SEND_RISK_ALERTS: bool = True
    SEND_DAILY_SUMMARY: bool = True


# ---------------------------------------------------------------------------
# Dashboard configuration
# ---------------------------------------------------------------------------
@dataclass
class DashboardConfig:
    """Web dashboard settings."""

    HOST: str = _env("DASHBOARD_HOST", "0.0.0.0")
    PORT: int = _env_int("DASHBOARD_PORT", 8080)
    WS_PORT: int = _env_int("DASHBOARD_WS_PORT", 8081)


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------
RISK = RiskConfig()
NADO = NadoConfig()
EXCHANGE_01 = Exchange01Config()
TELEGRAM = TelegramConfig()
DASHBOARD = DashboardConfig()

# Convenience aliases for fee calculations (taker assumed for small capital)
NADO_TAKER: float = NADO.TAKER_FEE_PCT       # 0.04%
EXCHANGE_01_TAKER: float = EXCHANGE_01.TAKER_FEE_PCT  # 0.05%


if __name__ == "__main__":
    print("=== Delta-Neutral Bot Configuration ===")
    print(f"DRY_RUN:            {RISK.DRY_RUN}")
    print(f"MAX_POSITION_USD:   ${RISK.MAX_POSITION_USD}")
    print(f"MIN_POSITION_USD:   ${RISK.MIN_POSITION_USD}")
    print(f"MAX_OPEN_POSITIONS: {RISK.MAX_OPEN_POSITIONS}")
    print(f"MAX_LEVERAGE:       {RISK.MAX_LEVERAGE}x")
    print(f"MIN_NET_APR_PCT:    {RISK.MIN_NET_APR_PCT}%")
    print(f"MAX_SPREAD_PCT:     {RISK.MAX_SPREAD_PCT}%")
    print(f"STOP_LOSS_PNL_PCT:  {RISK.STOP_LOSS_PNL_PCT}%")
    print(f"LIQ_BUFFER_PCT:     {RISK.LIQUIDATION_BUFFER_PCT}%")
    print(f"MAX_BREAKEVEN_HRS:  {RISK.MAX_BREAKEVEN_HOURS}h")
    print(f"Nado Gateway:       {NADO.GATEWAY_REST_V1}")
    print(f"01 Exchange URL:    {EXCHANGE_01.BASE_URL}")
    print(f"Monitored pairs:    {MONITORED_PAIRS}")
