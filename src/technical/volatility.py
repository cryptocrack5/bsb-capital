"""
BSB Capital - Volatility & Risk Module
Implements volatility regime detection and dynamic risk management.

Methodologies:
- GARCH(1,1) for volatility forecasting
- ATR for dynamic stop-loss calculation
- Choppiness Index for trend vs. range detection
- Volatility Regime Switching
- Maximum Drawdown analysis
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import (
    ATR_PERIOD, ATR_STOP_MULTIPLIER,
    CHOP_PERIOD, CHOP_TRENDING, CHOP_RANGING,
    GARCH_P, GARCH_Q,
    VOL_REGIME_HIGH, VOL_REGIME_LOW,
)
from src.models.schemas import VolatilityAnalysis, VolatilityRegime

logger = logging.getLogger(__name__)


class VolatilityEngine:
    """
    Analyzes market volatility and determines risk regime.

    The confidence adjustment factor reduces signal strength
    in high-volatility environments:

        confidence = 1 - (current_vol_percentile - 0.5) * 2
        clamped to [0.1, 1.0]
    """

    def analyze(self, df: pd.DataFrame) -> VolatilityAnalysis:
        """
        Run volatility analysis on OHLCV data.

        Args:
            df: DataFrame with [open, high, low, close] columns.
        """
        result = VolatilityAnalysis()

        if df is None or len(df) < 30:
            logger.warning("Insufficient data for volatility analysis")
            return result

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # ATR
        result.atr = self._compute_atr(high, low, close, ATR_PERIOD)
        if close[-1] > 0:
            result.atr_percentage = (result.atr / close[-1]) * 100

        # Historical Volatility (30-day annualized)
        result.historical_volatility_30d = self._compute_historical_volatility(
            close, 30
        )

        # Choppiness Index
        result.choppiness_index = self._compute_choppiness(
            high, low, close, CHOP_PERIOD
        )

        # GARCH forecast
        result.garch_forecast = self._garch_forecast(close)

        # Maximum Drawdown
        result.max_drawdown_30d = self._max_drawdown(close[-30:])
        result.max_drawdown_90d = self._max_drawdown(close[-90:]) if len(close) >= 90 else result.max_drawdown_30d

        # Risk-adjusted returns
        returns_30d = np.diff(close[-31:]) / close[-31:-1] if len(close) >= 31 else np.array([])
        if len(returns_30d) > 5:
            result.sharpe_ratio = self._sharpe_ratio(returns_30d)
            result.sortino_ratio = self._sortino_ratio(returns_30d)

        # Volatility regime
        result.market_regime = self._detect_regime(close)

        # Dynamic stop-loss
        result.dynamic_stop_loss = close[-1] - (result.atr * ATR_STOP_MULTIPLIER)

        # Confidence adjustment
        result.confidence_adjustment = self._compute_confidence(close)

        # Score (higher = less risky / better risk-adjusted)
        result.score = self._compute_score(result)

        return result

    def _compute_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int,
    ) -> float:
        """
        ATR = SMA of True Range over period.
        True Range = max(H-L, |H-Prev_C|, |L-Prev_C|)
        """
        if len(close) < period + 1:
            return 0.0

        tr_list = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
            tr_list.append(tr)

        if len(tr_list) < period:
            return np.mean(tr_list) if tr_list else 0.0

        # Wilder's smoothing for ATR
        atr = np.mean(tr_list[:period])
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period

        return round(atr, 6)

    def _compute_historical_volatility(
        self, prices: np.ndarray, window: int
    ) -> float:
        """
        Annualized historical volatility.
        HV = std(log returns) * sqrt(365)
        """
        if len(prices) < window + 1:
            return 0.0

        log_returns = np.diff(np.log(prices[-window - 1:]))
        if len(log_returns) == 0:
            return 0.0
        return round(float(np.std(log_returns) * np.sqrt(365) * 100), 2)

    def _compute_choppiness(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int,
    ) -> float:
        """
        Choppiness Index = 100 * LOG10(SUM(ATR,n) / (Highest-Lowest)) / LOG10(n)

        Interpretation:
        - > 61.8: Market is choppy/ranging
        - < 38.2: Market is trending
        """
        if len(close) < period + 1:
            return 50.0

        # Calculate sum of ATR(1) over period
        atr_sum = 0.0
        for i in range(-period, 0):
            idx = len(close) + i
            if idx > 0:
                tr = max(
                    high[idx] - low[idx],
                    abs(high[idx] - close[idx - 1]),
                    abs(low[idx] - close[idx - 1]),
                )
                atr_sum += tr

        highest = np.max(high[-period:])
        lowest = np.min(low[-period:])
        hl_range = highest - lowest

        if hl_range == 0 or period <= 1:
            return 50.0

        chop = 100 * np.log10(atr_sum / hl_range) / np.log10(period)
        return round(max(0, min(100, chop)), 2)

    def _garch_forecast(self, prices: np.ndarray) -> Optional[float]:
        """
        GARCH(1,1) volatility forecast.
        σ²(t+1) = ω + α*ε²(t) + β*σ²(t)

        Falls back to simple volatility if arch library unavailable.
        """
        if len(prices) < 100:
            return None

        returns = np.diff(np.log(prices)) * 100  # Scale for numerical stability

        try:
            from arch import arch_model
            model = arch_model(
                returns[-252:],  # Use last year
                vol="Garch",
                p=GARCH_P,
                q=GARCH_Q,
                mean="Zero",
                rescale=False,
            )
            fitted = model.fit(disp="off", show_warning=False)
            forecast = fitted.forecast(horizon=1)
            var_forecast = forecast.variance.values[-1, 0]
            vol_forecast = np.sqrt(var_forecast)
            return round(float(vol_forecast), 4)
        except Exception as e:
            logger.debug(f"GARCH model failed, using fallback: {e}")
            # Fallback: exponentially weighted volatility
            ewm_vol = pd.Series(returns).ewm(span=30).std().iloc[-1]
            return round(float(ewm_vol), 4) if not np.isnan(ewm_vol) else None

    def _max_drawdown(self, prices: np.ndarray) -> float:
        """
        Maximum drawdown = max peak-to-trough decline.
        Returns as percentage (negative number).
        """
        if len(prices) < 2:
            return 0.0

        peak = prices[0]
        max_dd = 0.0

        for price in prices[1:]:
            if price > peak:
                peak = price
            dd = (price - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd

        return round(max_dd, 2)

    def _sharpe_ratio(self, returns: np.ndarray, risk_free: float = 0.0) -> float:
        """
        Sharpe Ratio = (mean(R) - Rf) / std(R) * sqrt(365)
        """
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        excess = returns - risk_free / 365
        sharpe = np.mean(excess) / np.std(excess) * np.sqrt(365)
        return round(float(sharpe), 2)

    def _sortino_ratio(self, returns: np.ndarray, risk_free: float = 0.0) -> float:
        """
        Sortino Ratio = (mean(R) - Rf) / downside_std * sqrt(365)
        Only considers downside deviation.
        """
        if len(returns) < 2:
            return 0.0
        excess = returns - risk_free / 365
        downside = returns[returns < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return float(self._sharpe_ratio(returns, risk_free))
        sortino = np.mean(excess) / np.std(downside) * np.sqrt(365)
        return round(float(sortino), 2)

    def _detect_regime(self, prices: np.ndarray) -> VolatilityRegime:
        """
        Detect volatility regime using rolling volatility percentile.

        Regime thresholds:
        - Below 20th percentile: Low volatility
        - 20th-80th: Normal
        - Above 80th: High
        - Above 95th: Extreme
        """
        if len(prices) < 60:
            return VolatilityRegime.NORMAL

        # Rolling 30-day volatility
        returns = np.diff(np.log(prices))
        rolling_vol = []
        for i in range(30, len(returns)):
            vol = np.std(returns[i - 30:i])
            rolling_vol.append(vol)

        if not rolling_vol:
            return VolatilityRegime.NORMAL

        current_vol = rolling_vol[-1]
        percentile = sum(1 for v in rolling_vol if v <= current_vol) / len(rolling_vol)

        if percentile > 0.95:
            return VolatilityRegime.EXTREME
        if percentile > VOL_REGIME_HIGH:
            return VolatilityRegime.HIGH
        if percentile < VOL_REGIME_LOW:
            return VolatilityRegime.LOW
        return VolatilityRegime.NORMAL

    def _compute_confidence(self, prices: np.ndarray) -> float:
        """
        Compute confidence adjustment factor.
        Reduces trading confidence in high-volatility environments.

        confidence = clamp(1 - (vol_percentile - 0.5) * 2, 0.1, 1.0)
        """
        if len(prices) < 60:
            return 0.7

        returns = np.diff(np.log(prices))
        rolling_vol = []
        for i in range(30, len(returns)):
            vol = np.std(returns[i - 30:i])
            rolling_vol.append(vol)

        if not rolling_vol:
            return 0.7

        current_vol = rolling_vol[-1]
        percentile = sum(1 for v in rolling_vol if v <= current_vol) / len(rolling_vol)

        confidence = 1.0 - (percentile - 0.5) * 2
        return round(max(0.1, min(1.0, confidence)), 2)

    def _compute_score(self, analysis: VolatilityAnalysis) -> float:
        """Compute volatility score (0-100). Higher = less risky."""
        score = 50.0

        # Regime impact
        if analysis.market_regime == VolatilityRegime.LOW:
            score += 20
        elif analysis.market_regime == VolatilityRegime.NORMAL:
            score += 5
        elif analysis.market_regime == VolatilityRegime.HIGH:
            score -= 15
        elif analysis.market_regime == VolatilityRegime.EXTREME:
            score -= 30

        # Drawdown impact
        if analysis.max_drawdown_30d > -5:
            score += 10
        elif analysis.max_drawdown_30d > -15:
            score += 0
        elif analysis.max_drawdown_30d > -30:
            score -= 10
        else:
            score -= 20

        # Choppiness (trending markets are preferred)
        if analysis.choppiness_index < CHOP_TRENDING:
            score += 10  # Trending = easier to trade
        elif analysis.choppiness_index > CHOP_RANGING:
            score -= 5  # Choppy = harder

        # Sharpe ratio
        if analysis.sharpe_ratio is not None:
            if analysis.sharpe_ratio > 2:
                score += 10
            elif analysis.sharpe_ratio > 1:
                score += 5
            elif analysis.sharpe_ratio < 0:
                score -= 10

        return max(0, min(100, score))
