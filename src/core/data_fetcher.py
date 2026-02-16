"""
BSB Capital - Data Fetcher
Retrieves token data from CoinGecko and other APIs.
"""

import time
import logging
from typing import Optional

import requests
import pandas as pd

from config.settings import COINGECKO_BASE_URL, GITHUB_API_URL
from src.models.schemas import TokenMarketData, TokenType

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches market data, OHLCV, and metadata from public APIs."""

    def __init__(self, coingecko_api_key: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "BSB-Capital-Analyzer/1.0",
        })
        if coingecko_api_key:
            self.session.headers["x-cg-demo-api-key"] = coingecko_api_key
        self._rate_limit_delay = 1.5  # seconds between requests

    def _get(self, url: str, params: Optional[dict] = None) -> Optional[dict]:
        """Make a rate-limited GET request with retry logic."""
        for attempt in range(4):
            try:
                time.sleep(self._rate_limit_delay)
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt+1}/4): {e}")
                if attempt < 3:
                    time.sleep(2 ** (attempt + 1))
        return None

    def search_token(self, query: str) -> Optional[str]:
        """Search for a token and return its CoinGecko ID."""
        data = self._get(f"{COINGECKO_BASE_URL}/search", {"query": query})
        if not data or not data.get("coins"):
            return None
        # Return the first match
        return data["coins"][0]["id"]

    def get_token_data(self, token_id: str) -> Optional[TokenMarketData]:
        """Fetch comprehensive token data from CoinGecko."""
        data = self._get(
            f"{COINGECKO_BASE_URL}/coins/{token_id}",
            {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "true",
                "developer_data": "true",
            },
        )
        if not data:
            return None

        md = data.get("market_data", {})
        token = TokenMarketData(
            name=data.get("name", ""),
            symbol=data.get("symbol", "").upper(),
            coingecko_id=token_id,
            price_usd=md.get("current_price", {}).get("usd", 0),
            market_cap=md.get("market_cap", {}).get("usd", 0),
            fully_diluted_valuation=md.get("fully_diluted_valuation", {}).get("usd", 0) or 0,
            circulating_supply=md.get("circulating_supply", 0) or 0,
            total_supply=md.get("total_supply", 0) or 0,
            max_supply=md.get("max_supply"),
            volume_24h=md.get("total_volume", {}).get("usd", 0),
            price_change_24h=md.get("price_change_percentage_24h", 0) or 0,
            price_change_7d=md.get("price_change_percentage_7d", 0) or 0,
            price_change_30d=md.get("price_change_percentage_30d", 0) or 0,
            ath=md.get("ath", {}).get("usd", 0),
            ath_change_percentage=md.get("ath_change_percentage", {}).get("usd", 0),
            atl=md.get("atl", {}).get("usd", 0),
        )
        token.token_type = self._classify_token(data)
        return token

    def get_ohlcv(self, token_id: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for technical analysis."""
        data = self._get(
            f"{COINGECKO_BASE_URL}/coins/{token_id}/ohlc",
            {"vs_currency": "usd", "days": str(days)},
        )
        if not data:
            return None

        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def get_market_chart(self, token_id: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch price and volume history."""
        data = self._get(
            f"{COINGECKO_BASE_URL}/coins/{token_id}/market_chart",
            {"vs_currency": "usd", "days": str(days), "interval": "daily"},
        )
        if not data:
            return None

        prices = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
        volumes = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])

        prices["timestamp"] = pd.to_datetime(prices["timestamp"], unit="ms")
        volumes["timestamp"] = pd.to_datetime(volumes["timestamp"], unit="ms")

        df = prices.merge(volumes, on="timestamp", how="outer")
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df

    def get_community_data(self, token_id: str) -> dict:
        """Extract community and developer data from CoinGecko."""
        data = self._get(
            f"{COINGECKO_BASE_URL}/coins/{token_id}",
            {
                "localization": "false",
                "tickers": "false",
                "market_data": "false",
                "community_data": "true",
                "developer_data": "true",
            },
        )
        if not data:
            return {}
        return {
            "community": data.get("community_data", {}),
            "developer": data.get("developer_data", {}),
            "links": data.get("links", {}),
            "description": data.get("description", {}).get("en", ""),
            "categories": data.get("categories", []),
        }

    def get_github_repo_stats(self, repo_url: str) -> dict:
        """Fetch GitHub repository statistics."""
        # Extract owner/repo from URL
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 2:
            return {}
        owner, repo = parts[-2], parts[-1]

        stats = {}
        repo_data = self._get(f"{GITHUB_API_URL}/repos/{owner}/{repo}")
        if repo_data:
            stats["stars"] = repo_data.get("stargazers_count", 0)
            stats["forks"] = repo_data.get("forks_count", 0)
            stats["open_issues"] = repo_data.get("open_issues_count", 0)
            stats["language"] = repo_data.get("language", "")
            stats["updated_at"] = repo_data.get("updated_at", "")

        # Get commit activity
        commits = self._get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/stats/commit_activity"
        )
        if commits and isinstance(commits, list):
            recent_weeks = commits[-4:] if len(commits) >= 4 else commits
            stats["commits_4w"] = sum(w.get("total", 0) for w in recent_weeks)
            stats["commits_trend"] = self._compute_commit_trend(commits)

        # Get contributors count
        contribs = self._get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contributors",
            {"per_page": "1", "anon": "true"},
        )
        if contribs:
            stats["contributors"] = len(contribs)

        return stats

    def _classify_token(self, data: dict) -> TokenType:
        """Classify token type based on metadata."""
        categories = [c.lower() for c in data.get("categories", []) if c]
        desc = data.get("description", {}).get("en", "").lower()

        if any("layer 1" in c or "smart contract" in c for c in categories):
            return TokenType.L1
        if any("layer 2" in c or "scaling" in c or "rollup" in c for c in categories):
            return TokenType.L2
        if any("defi" in c or "decentralized finance" in c or "dex" in c or "lending" in c for c in categories):
            return TokenType.DEFI
        if any("gaming" in c or "metaverse" in c or "nft" in c for c in categories):
            return TokenType.GAMING
        if any("meme" in c for c in categories):
            return TokenType.MEME
        if any("stablecoin" in c for c in categories):
            return TokenType.STABLECOIN
        if "infrastructure" in desc or any("infrastructure" in c for c in categories):
            return TokenType.INFRASTRUCTURE
        return TokenType.UNKNOWN

    @staticmethod
    def _compute_commit_trend(weekly_data: list) -> str:
        """Compute commit trend from weekly data."""
        if len(weekly_data) < 8:
            return "insufficient_data"
        recent = sum(w.get("total", 0) for w in weekly_data[-4:])
        older = sum(w.get("total", 0) for w in weekly_data[-8:-4])
        if older == 0:
            return "new_activity" if recent > 0 else "inactive"
        ratio = recent / older
        if ratio > 1.2:
            return "increasing"
        if ratio < 0.8:
            return "decreasing"
        return "stable"
