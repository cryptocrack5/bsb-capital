"""
BSB Capital - Technical Indicators Module
Implements momentum indicators with crypto-optimized parameters.

Backtested parameters and methodologies based on:
- VWAP Volume Confirmation (institutional flow detection)
- RSI Divergence Detection (automated)
- Bollinger Bandwidth Squeeze Strategy
- Moving Average Crossover optimization for crypto markets
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import (
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_DIVERGENCE_LOOKBACK,
    BB_PERIOD, BB_STD_DEV, BB_SQUEEZE_THRESHOLD,
    MA_SHORT, MA_MEDIUM, MA_LONG,
    VWAP_VOLUME_MULTIPLIER,
)
from src.models.schemas import MomentumIndicators, TrendDirection

logger = logging.getLogger(__name__)


class TechnicalIndicatorEngine:
    """
    Computes technical indicators optimized for crypto markets.

    All indicators use parameters backtested on BTC/ETH data:
    - RSI(14) with divergence detection
    - VWAP with volume confirmation (>2x avg = significant)
    - Bollinger Bands(20, 2σ) with squeeze detection
    - MA crossover system (20/50/200)
    """

    def analyze(self, df: pd.DataFrame) -> MomentumIndicators:
        """
        Run technical indicator analysis on OHLCV data.

        Args:
            df: DataFrame with columns [open, high, low, close] and optionally [volume].
                Index should be datetime.
        """
        result = MomentumIndicators()

        if df is None or len(df) < MA_LONG:
            logger.warning("Insufficient data for full technical analysis")
            return result

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        has_volume = "volume" in df.columns
        volume = df["volume"].values if has_volume else None

        # RSI
        result.rsi = self._compute_rsi(close, RSI_PERIOD)
        result.rsi_signal = self._interpret_rsi(result.rsi)
        result.rsi_divergence = self._detect_rsi_divergence(
            close, RSI_PERIOD, RSI_DIVERGENCE_LOOKBACK
        )

        # MACD
        macd_data = self._compute_macd(close)
        result.macd_value = macd_data["macd"]
        result.macd_signal = macd_data["signal"]
        result.macd_histogram = macd_data["histogram"]
        result.macd_crossover = macd_data["crossover"]

        # VWAP (if volume available)
        if has_volume and volume is not None:
            result.vwap = self._compute_vwap(high, low, close, volume)
            current_price = close[-1]
            result.price_vs_vwap = "above" if current_price > result.vwap else "below"
            avg_volume = np.mean(volume[-20:])
            current_volume = volume[-1]
            result.vwap_volume_signal = (
                current_volume > avg_volume * VWAP_VOLUME_MULTIPLIER
            )

        # Bollinger Bands
        bb = self._compute_bollinger(close, BB_PERIOD, BB_STD_DEV)
        result.bb_upper = bb["upper"]
        result.bb_middle = bb["middle"]
        result.bb_lower = bb["lower"]
        result.bb_bandwidth = bb["bandwidth"]
        result.bb_squeeze = bb["bandwidth"] < BB_SQUEEZE_THRESHOLD

        # Moving Averages
        result.ma_20 = self._sma(close, MA_SHORT)
        result.ma_50 = self._sma(close, MA_MEDIUM)
        result.ma_200 = self._sma(close, MA_LONG)

        # Cross signals
        ma_short_series = pd.Series(close).rolling(MA_SHORT).mean()
        ma_long_series = pd.Series(close).rolling(MA_LONG).mean()
        if len(ma_short_series) >= 2 and len(ma_long_series) >= 2:
            prev_short = ma_short_series.iloc[-2]
            prev_long = ma_long_series.iloc[-2]
            curr_short = ma_short_series.iloc[-1]
            curr_long = ma_long_series.iloc[-1]
            if not (np.isnan(prev_short) or np.isnan(prev_long)):
                result.golden_cross = prev_short < prev_long and curr_short > curr_long
                result.death_cross = prev_short > prev_long and curr_short < curr_long

        # Overall trend
        result.trend = self._determine_trend(close, result)

        # Score
        result.score = self._compute_score(result)

        return result

    def _compute_rsi(self, prices: np.ndarray, period: int) -> float:
        """
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss over period
        Uses Wilder's smoothing method.
        """
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Wilder's smoothing
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def _interpret_rsi(self, rsi: float) -> str:
        """Interpret RSI level."""
        if rsi >= RSI_OVERBOUGHT:
            return "overbought"
        if rsi <= RSI_OVERSOLD:
            return "oversold"
        return "neutral"

    def _detect_rsi_divergence(
        self, prices: np.ndarray, rsi_period: int, lookback: int
    ) -> Optional[str]:
        """
        Detect RSI divergence.
        Bullish divergence: Price makes lower low, RSI makes higher low
        Bearish divergence: Price makes higher high, RSI makes lower high
        """
        if len(prices) < rsi_period + lookback + 1:
            return None

        # Compute RSI series
        rsi_series = []
        for i in range(lookback):
            end_idx = len(prices) - lookback + i + 1
            sub_prices = prices[:end_idx]
            rsi_val = self._compute_rsi(sub_prices, rsi_period)
            rsi_series.append(rsi_val)

        if len(rsi_series) < 2:
            return None

        price_window = prices[-lookback:]

        # Find local extremes
        price_low1 = np.min(price_window[:lookback // 2])
        price_low2 = np.min(price_window[lookback // 2:])
        rsi_low1 = min(rsi_series[:lookback // 2])
        rsi_low2 = min(rsi_series[lookback // 2:])

        price_high1 = np.max(price_window[:lookback // 2])
        price_high2 = np.max(price_window[lookback // 2:])
        rsi_high1 = max(rsi_series[:lookback // 2])
        rsi_high2 = max(rsi_series[lookback // 2:])

        # Bullish divergence: lower price low + higher RSI low
        if price_low2 < price_low1 and rsi_low2 > rsi_low1:
            return "bullish"

        # Bearish divergence: higher price high + lower RSI high
        if price_high2 > price_high1 and rsi_high2 < rsi_high1:
            return "bearish"

        return None

    def _compute_macd(
        self,
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ) -> dict:
        """Compute MACD, Signal line, and Histogram."""
        if len(prices) < slow + signal_period:
            return {"macd": 0, "signal": 0, "histogram": 0, "crossover": None}

        series = pd.Series(prices)
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        crossover = None
        if len(macd_line) >= 2:
            if macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]:
                crossover = "bullish"
            elif macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]:
                crossover = "bearish"

        return {
            "macd": round(macd_line.iloc[-1], 6),
            "signal": round(signal_line.iloc[-1], 6),
            "histogram": round(histogram.iloc[-1], 6),
            "crossover": crossover,
        }

    def _compute_vwap(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> float:
        """
        VWAP = Σ(Typical Price * Volume) / Σ(Volume)
        Typical Price = (High + Low + Close) / 3

        Uses last 20 periods for rolling VWAP.
        """
        n = min(20, len(close))
        typical = (high[-n:] + low[-n:] + close[-n:]) / 3
        vol = volume[-n:]
        total_vol = np.sum(vol)
        if total_vol == 0:
            return close[-1]
        vwap = np.sum(typical * vol) / total_vol
        return round(vwap, 6)

    def _compute_bollinger(
        self, prices: np.ndarray, period: int, std_dev: float
    ) -> dict:
        """
        Bollinger Bands:
        Middle = SMA(period)
        Upper = Middle + std_dev * σ
        Lower = Middle - std_dev * σ
        Bandwidth = (Upper - Lower) / Middle
        """
        if len(prices) < period:
            p = prices[-1]
            return {"upper": p, "middle": p, "lower": p, "bandwidth": 0}

        window = prices[-period:]
        middle = np.mean(window)
        std = np.std(window)
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        bandwidth = (upper - lower) / middle if middle != 0 else 0

        return {
            "upper": round(upper, 6),
            "middle": round(middle, 6),
            "lower": round(lower, 6),
            "bandwidth": round(bandwidth, 4),
        }

    def _sma(self, prices: np.ndarray, period: int) -> float:
        """Simple Moving Average."""
        if len(prices) < period:
            return prices[-1] if len(prices) > 0 else 0
        return round(np.mean(prices[-period:]), 6)

    def _determine_trend(
        self, prices: np.ndarray, indicators: MomentumIndicators
    ) -> TrendDirection:
        """Determine overall trend from multiple signals."""
        bullish_signals = 0
        bearish_signals = 0

        # Price vs MAs
        current = prices[-1]
        if current > indicators.ma_50:
            bullish_signals += 1
        else:
            bearish_signals += 1

        if current > indicators.ma_200:
            bullish_signals += 1
        else:
            bearish_signals += 1

        # MA alignment
        if indicators.ma_20 > indicators.ma_50 > indicators.ma_200:
            bullish_signals += 2
        elif indicators.ma_20 < indicators.ma_50 < indicators.ma_200:
            bearish_signals += 2

        # MACD
        if indicators.macd_histogram > 0:
            bullish_signals += 1
        else:
            bearish_signals += 1

        # RSI
        if indicators.rsi > 50:
            bullish_signals += 1
        elif indicators.rsi < 50:
            bearish_signals += 1

        if bullish_signals >= bearish_signals + 2:
            return TrendDirection.BULLISH
        if bearish_signals >= bullish_signals + 2:
            return TrendDirection.BEARISH
        return TrendDirection.SIDEWAYS

    def _compute_score(self, indicators: MomentumIndicators) -> float:
        """Compute momentum score (0-100). 50 = neutral."""
        score = 50.0

        # Trend (+/- 20)
        if indicators.trend == TrendDirection.BULLISH:
            score += 20
        elif indicators.trend == TrendDirection.BEARISH:
            score -= 20

        # RSI (+/- 10)
        if indicators.rsi_signal == "oversold":
            score += 10  # Potential reversal up
        elif indicators.rsi_signal == "overbought":
            score -= 10

        # RSI Divergence (+/- 10)
        if indicators.rsi_divergence == "bullish":
            score += 10
        elif indicators.rsi_divergence == "bearish":
            score -= 10

        # MACD crossover (+/- 5)
        if indicators.macd_crossover == "bullish":
            score += 5
        elif indicators.macd_crossover == "bearish":
            score -= 5

        # VWAP signal (+/- 5)
        if indicators.price_vs_vwap == "above" and indicators.vwap_volume_signal:
            score += 5
        elif indicators.price_vs_vwap == "below" and indicators.vwap_volume_signal:
            score -= 5

        # Golden/Death cross (+/- 10)
        if indicators.golden_cross:
            score += 10
        elif indicators.death_cross:
            score -= 10

        # BB squeeze (+5 neutral - preparing for move)
        if indicators.bb_squeeze:
            score += 3  # Slight positive bias - breakout expected

        return max(0, min(100, score))
