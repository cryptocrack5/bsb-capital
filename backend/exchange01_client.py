"""
Client for 01 Exchange (Solana) local REST API.
The API runs locally — if unreachable, falls back to mock mode.
"""

import logging
import random
import time
from typing import Dict, List, Optional

import requests

from config import EXCHANGE_01, RISK, MONITORED_PAIRS

logger = logging.getLogger(__name__)


class Exchange01Client:
    """Client for the 01 Exchange local REST API on Solana."""

    def __init__(self) -> None:
        self.base_url: str = EXCHANGE_01.BASE_URL.rstrip("/")
        self.mock_mode: bool = False
        self._price_cache: Dict[str, tuple[float, float]] = {}
        self._cache_ttl = 5.0
        self._timeout = 10

    # -----------------------------------------------------------------------
    # HTTP helper
    # -----------------------------------------------------------------------
    def _get(self, path: str) -> dict:
        """GET request to the local 01 API."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("01 Exchange GET %s failed: %s", path, exc)
            raise

    def _post(self, path: str, body: dict) -> dict:
        """POST request to the local 01 API."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=body, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("01 Exchange POST %s failed: %s", path, exc)
            raise

    def _delete(self, path: str, body: Optional[dict] = None) -> dict:
        """DELETE request to the local 01 API."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.delete(url, json=body, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("01 Exchange DELETE %s failed: %s", path, exc)
            raise

    # -----------------------------------------------------------------------
    # Mock data generators
    # -----------------------------------------------------------------------
    def _mock_prices(self) -> Dict[str, float]:
        return {
            "BTC-PERP": 97500.0 * (1 + random.uniform(-0.05, 0.05)),
            "ETH-PERP": 3250.0 * (1 + random.uniform(-0.05, 0.05)),
            "SOL-PERP": 185.0 * (1 + random.uniform(-0.05, 0.05)),
        }

    def _mock_funding(self, symbol: str) -> float:
        """Return mock hourly funding rate as APR with noise."""
        base_rates = {"BTC-PERP": 38.0, "ETH-PERP": 35.0, "SOL-PERP": 42.0}
        base = base_rates.get(symbol, 30.0)
        return base * (1 + random.uniform(-0.15, 0.15))

    def _mock_orderbook(self, symbol: str) -> dict:
        prices = self._mock_prices()
        mid = prices.get(symbol, 3000.0)
        spread_pct = random.uniform(0.01, 0.05)
        half_spread = mid * spread_pct / 100 / 2
        return {
            "best_bid": mid - half_spread,
            "best_ask": mid + half_spread,
            "mid": mid,
            "spread_pct": spread_pct,
            "depth_usd": random.uniform(15000, 50000),
        }

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------
    def health_check(self) -> bool:
        """Check if the local 01 API is reachable. Falls back to mock mode."""
        try:
            self._get("/markets")
            self.mock_mode = False
            logger.info("01 Exchange API: connected at %s", self.base_url)
            return True
        except Exception as exc:
            logger.warning(
                "01 Exchange API unreachable (%s) — activating mock mode", exc
            )
            self.mock_mode = True
            return False

    # -----------------------------------------------------------------------
    # Market data
    # -----------------------------------------------------------------------
    def get_funding(self, symbol: str) -> float:
        """Get current funding rate as APR for a symbol."""
        if self.mock_mode:
            rate = self._mock_funding(symbol)
            logger.debug("[MOCK] 01 Exchange funding %s: %.2f%% APR", symbol, rate)
            return rate

        try:
            data = self._get(f"/markets/{symbol}/funding")
            hourly_rate = float(data.get("fundingRate", data.get("rate", 0)))
            apr = hourly_rate * 24 * 365 * 100
            return apr
        except Exception as exc:
            logger.error("Failed to get 01 funding for %s: %s — using mock", symbol, exc)
            return self._mock_funding(symbol)

    def get_funding_rates(self) -> Dict[str, float]:
        """Get funding rates as APR for all monitored pairs."""
        rates: Dict[str, float] = {}
        for pair in MONITORED_PAIRS:
            rates[pair] = self.get_funding(pair)
        return rates

    def get_orderbook(self, symbol: str) -> dict:
        """Get orderbook with spread and depth for a symbol."""
        if self.mock_mode:
            ob = self._mock_orderbook(symbol)
            logger.debug("[MOCK] 01 Exchange orderbook %s: spread=%.4f%%", symbol, ob["spread_pct"])
            return ob

        try:
            data = self._get(f"/markets/{symbol}/orderbook")
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            best_bid = float(bids[0]["price"]) if bids else 0
            best_ask = float(asks[0]["price"]) if asks else 0
            mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
            spread_pct = ((best_ask - best_bid) / mid * 100) if mid > 0 else 0

            bid_depth = sum(float(b.get("price", 0)) * float(b.get("size", 0)) for b in bids[:5])
            ask_depth = sum(float(a.get("price", 0)) * float(a.get("size", 0)) for a in asks[:5])

            return {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "mid": mid,
                "spread_pct": spread_pct,
                "depth_usd": min(bid_depth, ask_depth),
            }
        except Exception as exc:
            logger.error("Failed to get 01 orderbook for %s: %s — using mock", symbol, exc)
            return self._mock_orderbook(symbol)

    def get_market_price(self, symbol: str) -> float:
        """Get current market price with caching."""
        cached = self._price_cache.get(symbol)
        if cached and (time.time() - cached[1]) < self._cache_ttl:
            return cached[0]

        if self.mock_mode:
            price = self._mock_prices().get(symbol, 0)
            self._price_cache[symbol] = (price, time.time())
            return price

        try:
            ob = self.get_orderbook(symbol)
            price = ob["mid"]
            if price > 0:
                self._price_cache[symbol] = (price, time.time())
            return price
        except Exception:
            if cached:
                return cached[0]
            return self._mock_prices().get(symbol, 0)

    # -----------------------------------------------------------------------
    # Account data
    # -----------------------------------------------------------------------
    def get_position(self) -> List[dict]:
        """Get open positions from the 01 Exchange account."""
        if self.mock_mode:
            logger.debug("[MOCK] 01 Exchange positions: empty")
            return []

        try:
            data = self._get("/position")
            positions = data if isinstance(data, list) else data.get("positions", [])
            return positions
        except Exception as exc:
            logger.error("Failed to get 01 positions: %s", exc)
            return []

    def get_balance(self) -> float:
        """Get USDC balance from the 01 Exchange account."""
        if self.mock_mode:
            balance = 500.0 * (1 + random.uniform(-0.02, 0.02))
            logger.debug("[MOCK] 01 Exchange balance: $%.2f", balance)
            return balance

        try:
            data = self._get("/balance")
            return float(data.get("balance", data.get("usdc", 0)))
        except Exception as exc:
            logger.error("Failed to get 01 balance: %s", exc)
            return 0.0

    # -----------------------------------------------------------------------
    # Trading
    # -----------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        current_price: float,
        reduce_only: bool = False,
    ) -> dict:
        """Place a market order on 01 Exchange.

        Args:
            symbol: e.g. "ETH-PERP"
            side: "buy" (long) or "sell" (short)
            size_usd: notional value in USD
            current_price: current market price for token size calculation
            reduce_only: True when closing a position
        """
        size_tokens = size_usd / current_price if current_price > 0 else 0

        order_info = {
            "protocol": "01",
            "symbol": symbol,
            "side": side,
            "size_usd": size_usd,
            "size_tokens": size_tokens,
            "price": current_price,
            "reduce_only": reduce_only,
        }

        if RISK.DRY_RUN:
            logger.info("[DRY RUN] 01 Exchange order: %s", order_info)
            fill_price = current_price * (1 + random.uniform(-0.0001, 0.0001))
            return {
                "status": "simulated",
                "fill_price": fill_price,
                "size_tokens": size_tokens,
                **order_info,
            }

        if self.mock_mode:
            logger.info("[MOCK] 01 Exchange order simulated: %s", order_info)
            fill_price = current_price * (1 + random.uniform(-0.0001, 0.0001))
            return {
                "status": "mock",
                "fill_price": fill_price,
                "size_tokens": size_tokens,
                **order_info,
            }

        try:
            body = {
                "symbol": symbol,
                "orderType": "market",
                "side": side,
                "size": size_tokens,
                "price": None,
            }
            if reduce_only:
                body["reduceOnly"] = True

            result = self._post("/order", body)
            logger.info("01 Exchange order placed: %s -> %s", order_info, result)
            return {"status": "filled", "result": result, **order_info}
        except Exception as exc:
            logger.error("01 Exchange order failed: %s — %s", order_info, exc)
            return {"error": str(exc), **order_info}

    def close_position(self, symbol: str, size_tokens: float, side: str) -> dict:
        """Close a position by placing an opposite reduce-only order."""
        price = self.get_market_price(symbol)
        close_side = "sell" if side == "buy" else "buy"
        size_usd = size_tokens * price
        return self.place_order(symbol, close_side, size_usd, price, reduce_only=True)

    @property
    def is_connected(self) -> bool:
        return not self.mock_mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    client = Exchange01Client()

    print("=== 01 Exchange Client Test ===")
    ok = client.health_check()
    print(f"Connected: {ok} (mock_mode: {client.mock_mode})")

    for pair in MONITORED_PAIRS:
        rate = client.get_funding(pair)
        price = client.get_market_price(pair)
        ob = client.get_orderbook(pair)
        print(f"{pair}: funding={rate:.1f}% APR, price=${price:.2f}, spread={ob['spread_pct']:.4f}%")

    balance = client.get_balance()
    print(f"Balance: ${balance:.2f}")
    positions = client.get_position()
    print(f"Positions: {positions}")
