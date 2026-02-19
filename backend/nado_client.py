"""
Async client for Nado Finance (Ink L2) — REST + WebSocket.
Handles public market data and authenticated trading via the nado-protocol SDK.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

import aiohttp

from config import NADO, RISK, MONITORED_PAIRS

logger = logging.getLogger(__name__)

# x18 format helper
X18 = 10**18


def _from_x18(value: str | int) -> float:
    """Convert an x18-encoded value to a regular float."""
    return int(str(value)) / X18


def _to_x18(value: float) -> str:
    """Convert a regular float to x18 string."""
    return str(int(value * X18))


class NadoClient:
    """Async client for Nado Finance on Ink L2."""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._sdk_client: Optional[Any] = None
        self.product_id_map: Dict[str, int] = {}
        self._price_cache: Dict[str, tuple[float, float]] = {}  # pair -> (price, timestamp)
        self._cache_ttl = 5.0
        self._connected = False
        self._ws_running = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close all connections."""
        self._ws_running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("NadoClient connections closed")

    # -----------------------------------------------------------------------
    # HTTP helpers with retry
    # -----------------------------------------------------------------------
    async def _get(self, url: str, params: Optional[dict] = None) -> Any:
        """GET request with 3 retries and exponential backoff."""
        delays = [1, 2, 4]
        last_err: Optional[Exception] = None
        session = await self._get_session()
        for attempt, delay in enumerate(delays, 1):
            try:
                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    logger.debug("GET %s -> %d", url, resp.status)
                    return data
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "GET %s attempt %d failed: %s — retrying in %ds",
                    url, attempt, exc, delay,
                )
                if attempt < len(delays):
                    await asyncio.sleep(delay)
        logger.error("GET %s failed after %d attempts: %s", url, len(delays), last_err)
        raise last_err  # type: ignore[misc]

    async def _post(self, url: str, body: dict) -> Any:
        """POST request with 3 retries."""
        delays = [1, 2, 4]
        last_err: Optional[Exception] = None
        session = await self._get_session()
        for attempt, delay in enumerate(delays, 1):
            try:
                async with session.post(url, json=body) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    logger.debug("POST %s -> %d", url, resp.status)
                    return data
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "POST %s attempt %d failed: %s — retrying in %ds",
                    url, attempt, exc, delay,
                )
                if attempt < len(delays):
                    await asyncio.sleep(delay)
        logger.error("POST %s failed after %d attempts: %s", url, len(delays), last_err)
        raise last_err  # type: ignore[misc]

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------
    async def initialize(self) -> None:
        """Load product map and optionally init SDK client."""
        await self._load_product_map()
        self._init_sdk()
        self._connected = True
        logger.info("NadoClient initialized — products: %s", self.product_id_map)

    async def _load_product_map(self) -> None:
        """Fetch all products and build symbol -> product_id mapping."""
        try:
            url = f"{NADO.GATEWAY_REST_V1}/query"
            data = await self._get(url, params={"type": "all_products"})
            products = data if isinstance(data, list) else data.get("data", data.get("products", []))
            for p in products:
                pid = p.get("product_id", p.get("id"))
                symbol = p.get("symbol", p.get("ticker", ""))
                if pid is not None and symbol:
                    # Perp products typically have odd product_ids
                    self.product_id_map[symbol] = int(pid)
            # Map our monitored pairs
            for pair in MONITORED_PAIRS:
                if pair not in self.product_id_map:
                    # Try alternate naming
                    base = pair.replace("-PERP", "")
                    for key in list(self.product_id_map.keys()):
                        if base in key.upper():
                            self.product_id_map[pair] = self.product_id_map[key]
                            break
        except Exception as exc:
            logger.error("Failed to load Nado products: %s — using defaults", exc)
            self.product_id_map = {"BTC-PERP": 3, "ETH-PERP": 5, "SOL-PERP": 7}

    def _init_sdk(self) -> None:
        """Initialize the nado-protocol SDK client for trading."""
        if not NADO.PRIVATE_KEY:
            logger.warning("No NADO_PRIVATE_KEY set — trading disabled")
            return
        try:
            from nado_protocol.client import create_nado_client, NadoClientMode
            self._sdk_client = create_nado_client(NadoClientMode.MAINNET, NADO.PRIVATE_KEY)
            logger.info("Nado SDK client initialized")
        except ImportError:
            logger.warning("nado-protocol SDK not installed — trading disabled")
        except Exception as exc:
            logger.error("Failed to init Nado SDK: %s", exc)

    # -----------------------------------------------------------------------
    # Public market data
    # -----------------------------------------------------------------------
    async def get_funding_rates(self) -> Dict[str, float]:
        """Get current funding rates as APR for each monitored pair."""
        rates: Dict[str, float] = {}
        try:
            url = f"{NADO.GATEWAY_REST_V2}/apr"
            data = await self._get(url)
            items = data if isinstance(data, list) else data.get("data", [])
            for item in items:
                symbol = item.get("symbol", item.get("pair", ""))
                # hourly rate -> APR
                hourly = float(item.get("funding_rate", item.get("rate", 0)))
                apr = hourly * 24 * 365 * 100
                for pair in MONITORED_PAIRS:
                    if pair in symbol or pair.replace("-PERP", "") in symbol:
                        rates[pair] = apr
                        break
        except Exception as exc:
            logger.error("Failed to get Nado funding rates: %s", exc)
            # Try archive endpoint as fallback
            try:
                rates = await self._get_funding_from_archive()
            except Exception as exc2:
                logger.error("Archive fallback also failed: %s", exc2)
        return rates

    async def _get_funding_from_archive(self) -> Dict[str, float]:
        """Fallback: get funding from archive endpoint."""
        rates: Dict[str, float] = {}
        for pair in MONITORED_PAIRS:
            pid = self.product_id_map.get(pair)
            if pid is None:
                continue
            try:
                data = await self._post(
                    f"{NADO.ARCHIVE_V1}",
                    {"type": "funding_rate", "product_id": pid},
                )
                items = data if isinstance(data, list) else data.get("data", [])
                if items:
                    latest = items[-1] if isinstance(items, list) else items
                    rate_val = latest.get("funding_rate", latest.get("rate", "0"))
                    hourly = _from_x18(rate_val) if isinstance(rate_val, str) and len(str(rate_val)) > 10 else float(rate_val)
                    rates[pair] = hourly * 24 * 365 * 100
            except Exception as exc:
                logger.warning("Archive funding for %s failed: %s", pair, exc)
        return rates

    async def get_tickers(self) -> Dict[str, dict]:
        """Get bid/ask prices for all monitored pairs."""
        tickers: Dict[str, dict] = {}
        try:
            url = f"{NADO.GATEWAY_REST_V2}/tickers"
            data = await self._get(url)
            items = data if isinstance(data, list) else data.get("data", [])
            for item in items:
                symbol = item.get("symbol", item.get("pair", ""))
                for pair in MONITORED_PAIRS:
                    if pair in symbol or pair.replace("-PERP", "") in symbol:
                        bid = float(item.get("best_bid", item.get("bid", 0)))
                        ask = float(item.get("best_ask", item.get("ask", 0)))
                        last_price = float(item.get("last_price", item.get("mark_price", (bid + ask) / 2 if bid and ask else 0)))
                        tickers[pair] = {"bid": bid, "ask": ask, "last": last_price}
                        self._price_cache[pair] = (last_price, time.time())
                        break
        except Exception as exc:
            logger.error("Failed to get Nado tickers: %s", exc)
        return tickers

    async def get_orderbook(self, symbol: str) -> dict:
        """Get orderbook for a symbol — returns spread and depth info."""
        try:
            url = f"{NADO.GATEWAY_REST_V2}/orderbook"
            data = await self._get(url, params={"symbol": symbol})
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            best_bid = float(bids[0][0]) if bids else 0
            best_ask = float(asks[0][0]) if asks else 0
            mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
            spread_pct = ((best_ask - best_bid) / mid * 100) if mid > 0 else 0

            # Depth: sum of top 5 levels in USD
            bid_depth = sum(float(b[0]) * float(b[1]) for b in bids[:5]) if bids else 0
            ask_depth = sum(float(a[0]) * float(a[1]) for a in asks[:5]) if asks else 0

            return {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "mid": mid,
                "spread_pct": spread_pct,
                "bid_depth_usd": bid_depth,
                "ask_depth_usd": ask_depth,
                "depth_usd": min(bid_depth, ask_depth),
            }
        except Exception as exc:
            logger.error("Failed to get Nado orderbook for %s: %s", symbol, exc)
            return {
                "best_bid": 0, "best_ask": 0, "mid": 0,
                "spread_pct": 0, "bid_depth_usd": 0,
                "ask_depth_usd": 0, "depth_usd": 0,
            }

    async def get_market_price(self, pair: str) -> float:
        """Get current market/mark price for a pair, with caching."""
        cached = self._price_cache.get(pair)
        if cached and (time.time() - cached[1]) < self._cache_ttl:
            return cached[0]

        pid = self.product_id_map.get(pair)
        if pid is None:
            logger.warning("Unknown product for %s", pair)
            return 0.0

        try:
            url = f"{NADO.GATEWAY_REST_V1}/query"
            data = await self._get(url, params={"type": "market_price", "product_id": pid})
            price_raw = data.get("market_price", data.get("price", data.get("data", "0")))
            if isinstance(price_raw, str) and len(price_raw) > 10:
                price = _from_x18(price_raw)
            else:
                price = float(price_raw)
            self._price_cache[pair] = (price, time.time())
            return price
        except Exception as exc:
            logger.error("Failed to get Nado price for %s: %s", pair, exc)
            if cached:
                return cached[0]
            return 0.0

    # -----------------------------------------------------------------------
    # Authenticated trading
    # -----------------------------------------------------------------------
    async def get_balance(self) -> float:
        """Get available USDT0 balance from the subaccount."""
        if self._sdk_client is None:
            logger.warning("SDK not initialized — cannot get balance")
            return 0.0
        try:
            info = self._sdk_client.subaccount.get_subaccount_info()
            # Extract USDT0 balance from subaccount info
            balances = info.get("balances", info.get("collaterals", []))
            for b in balances:
                asset = b.get("asset", b.get("symbol", ""))
                if "USDT" in asset.upper() or "USD" in asset.upper():
                    return float(b.get("amount", b.get("balance", 0)))
            # If structured differently, try total equity
            return float(info.get("equity", info.get("total_balance", 0)))
        except Exception as exc:
            logger.error("Failed to get Nado balance: %s", exc)
            return 0.0

    async def get_open_positions(self) -> List[dict]:
        """Get open positions from the subaccount."""
        if self._sdk_client is None:
            return []
        try:
            positions = self._sdk_client.subaccount.get_subaccount_info().get("positions", [])
            result = []
            for p in positions:
                size = float(p.get("amount", p.get("size", 0)))
                if abs(size) > 0:
                    result.append({
                        "product_id": p.get("product_id"),
                        "symbol": p.get("symbol", ""),
                        "size": size,
                        "side": "long" if size > 0 else "short",
                        "entry_price": float(p.get("entry_price", 0)),
                        "liq_price": float(p.get("liquidation_price", 0)),
                        "unrealized_pnl": float(p.get("unrealized_pnl", 0)),
                    })
            return result
        except Exception as exc:
            logger.error("Failed to get Nado positions: %s", exc)
            return []

    async def place_order(
        self,
        pair: str,
        side: str,
        size_usd: float,
        current_price: float,
        reduce_only: bool = False,
    ) -> dict:
        """Place a market order on Nado.

        Args:
            pair: e.g. "ETH-PERP"
            side: "buy" (long) or "sell" (short)
            size_usd: notional value in USD
            current_price: current market price for size calculation
            reduce_only: True when closing a position
        """
        product_id = self.product_id_map.get(pair)
        if product_id is None:
            return {"error": f"Unknown pair {pair}"}

        size_tokens = size_usd / current_price if current_price > 0 else 0
        amount_x18 = int(size_tokens * X18)
        if side == "sell":
            amount_x18 = -amount_x18

        order_info = {
            "protocol": "nado",
            "pair": pair,
            "side": side,
            "size_usd": size_usd,
            "size_tokens": size_tokens,
            "price": current_price,
            "reduce_only": reduce_only,
        }

        if RISK.DRY_RUN:
            logger.info("[DRY RUN] Nado order: %s", order_info)
            import random
            fill_price = current_price * (1 + random.uniform(-0.0001, 0.0001))
            return {
                "status": "simulated",
                "fill_price": fill_price,
                "size_tokens": size_tokens,
                **order_info,
            }

        if self._sdk_client is None:
            return {"error": "SDK not initialized", **order_info}

        try:
            result = self._sdk_client.market.place_order({
                "product_id": product_id,
                "price_x18": "0",  # market order
                "amount_x18": str(amount_x18),
                "expiration": str(int(time.time()) + 60),
                "nonce": str(int(time.time() * 1000)),
                "order_type": "market",
                "reduce_only": reduce_only,
            })
            logger.info("Nado order placed: %s -> %s", order_info, result)
            return {"status": "filled", "result": result, **order_info}
        except Exception as exc:
            logger.error("Nado order failed: %s — %s", order_info, exc)
            return {"error": str(exc), **order_info}

    async def close_position(self, pair: str, size_tokens: float, side: str) -> dict:
        """Close a position by placing an opposite reduce-only order."""
        price = await self.get_market_price(pair)
        close_side = "sell" if side == "buy" else "buy"
        size_usd = size_tokens * price
        return await self.place_order(pair, close_side, size_usd, price, reduce_only=True)

    # -----------------------------------------------------------------------
    # WebSocket streaming
    # -----------------------------------------------------------------------
    async def subscribe_market_data(
        self,
        on_funding_rate: Optional[Callable[..., Coroutine]] = None,
        on_best_bid_offer: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """Subscribe to real-time funding rates and BBO via WebSocket."""
        self._ws_running = True
        backoff = 1
        max_backoff = 60

        while self._ws_running:
            try:
                session = await self._get_session()
                async with session.ws_connect(NADO.SUBSCRIBE_WS, heartbeat=30) as ws:
                    self._ws = ws
                    backoff = 1
                    logger.info("Nado WebSocket connected")

                    # Subscribe to funding rates
                    await ws.send_json({
                        "method": "subscribe",
                        "stream": {"type": "funding_rate", "product_id": None},
                        "id": 1,
                    })
                    # Subscribe to best bid/offer
                    await ws.send_json({
                        "method": "subscribe",
                        "stream": {"type": "best_bid_offer", "product_id": None},
                        "id": 2,
                    })

                    async for msg in ws:
                        if not self._ws_running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            stream_type = data.get("stream", {}).get("type", data.get("type", ""))
                            if stream_type == "funding_rate" and on_funding_rate:
                                await on_funding_rate(data)
                            elif stream_type == "best_bid_offer" and on_best_bid_offer:
                                await on_best_bid_offer(data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break

            except asyncio.CancelledError:
                self._ws_running = False
                break
            except Exception as exc:
                logger.warning("Nado WS disconnected: %s — reconnecting in %ds", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        logger.info("Nado WebSocket subscription stopped")

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------
    async def health_check(self) -> bool:
        """Check connectivity to Nado API."""
        try:
            url = f"{NADO.GATEWAY_REST_V2}/tickers"
            await self._get(url)
            self._connected = True
            return True
        except Exception as exc:
            logger.error("Nado health check failed: %s", exc)
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected


if __name__ == "__main__":
    import asyncio as _asyncio

    logging.basicConfig(level=logging.DEBUG)

    async def _test() -> None:
        client = NadoClient()
        try:
            ok = await client.health_check()
            print(f"Nado health: {'OK' if ok else 'FAIL'}")
            if ok:
                await client.initialize()
                print(f"Products: {client.product_id_map}")
                rates = await client.get_funding_rates()
                print(f"Funding rates: {rates}")
                tickers = await client.get_tickers()
                print(f"Tickers: {tickers}")
        finally:
            await client.close()

    _asyncio.run(_test())
