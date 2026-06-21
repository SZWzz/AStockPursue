"""Technical indicator computation — single source of truth.

Used by:
  - IndicatorNode (workflow)
  - IndicatorLab API /generate endpoint (built-in presets)
"""

from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Presets ────────────────────────────────────────────────────────────────

PRESET_INDICATORS: Dict[str, List[str]] = {
    "all":          ["rsi", "sma_20", "sma_60", "ret_1d", "ret_5d", "ret_20d", "vol_ratio", "high_low_ratio", "volatility_20"],
    "momentum":     ["rsi", "ret_1d", "ret_5d", "ret_20d"],
    "moving_avg":   ["sma_20", "sma_60"],
    "volatility":   ["volatility_20", "high_low_ratio"],
    "volume":       ["vol_ratio"],
}


class IndicatorEngine:
    """Stateless indicator computation engine.

    All methods are pure functions of DataFrames — no internal state,
    no data fetching.  Panel construction from OHLCV dicts is provided
    as a convenience.
    """

    # ── Panel construction ────────────────────────────────────────────────

    @staticmethod
    def build_panels(
        ohlcv_data: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        """Build wide DataFrames for each OHLCV column from per-code dict.

        Args:
            ohlcv_data: {code: DataFrame(open, high, low, close, volume)}.

        Returns:
            {"close": DataFrame, "volume": DataFrame, "high": DataFrame, "low": DataFrame}
            Only columns present in the input data are included.
        """
        if isinstance(ohlcv_data, pd.DataFrame):
            ohlcv_data = {"panel": ohlcv_data}

        collectors: dict[str, List[pd.Series]] = {}
        for code, df in ohlcv_data.items():
            if not isinstance(df, pd.DataFrame):
                continue
            for col in ["close", "volume", "high", "low"]:
                if col in df.columns:
                    s = df[col].copy()
                    s.name = code
                    collectors.setdefault(col, []).append(s)

        panels: dict[str, pd.DataFrame] = {}
        for col, series_list in collectors.items():
            if series_list:
                df = pd.concat(series_list, axis=1)
                panels[col] = df.ffill()

        return panels

    # ── RSI (Wilder smoothing) ────────────────────────────────────────────

    @staticmethod
    def rsi(close: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Relative Strength Index with Wilder smoothing.

        Args:
            close: Wide DataFrame (dates × codes).
            period: RSI lookback period (default 14).

        Returns:
            RSI values (0–100) as a wide DataFrame.
        """
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(period, min_periods=period).mean()
        avg_loss = loss.rolling(period, min_periods=period).mean()

        # Wilder smoothing after initial SMA
        for i in range(period, len(avg_gain)):
            avg_gain.iloc[i] = (
                avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]
            ) / period
            avg_loss.iloc[i] = (
                avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]
            ) / period

        rs = avg_gain / avg_loss.replace(0, 1e-9)
        result = 100.0 - (100.0 / (1.0 + rs))
        result.columns = [f"{c}__rsi_{period}" for c in result.columns]
        return result

    # ── SMA ───────────────────────────────────────────────────────────────

    @staticmethod
    def sma(close: pd.DataFrame, window: int) -> pd.DataFrame:
        """Simple Moving Average.

        Args:
            close: Wide DataFrame (dates × codes).
            window: Rolling window size.

        Returns:
            SMA values as a wide DataFrame.
        """
        result = close.rolling(window, min_periods=window).mean()
        result.columns = [f"{c}__sma_{window}" for c in result.columns]
        return result

    # ── Returns ───────────────────────────────────────────────────────────

    @staticmethod
    def returns(close: pd.DataFrame, period: int) -> pd.DataFrame:
        """Percentage change over N periods.

        Args:
            close: Wide DataFrame (dates × codes).
            period: Lookback periods.

        Returns:
            Percentage returns as a wide DataFrame.
        """
        result = close.pct_change(period)
        result.columns = [f"{c}__ret_{period}d" for c in result.columns]
        return result

    # ── Volume ratio ──────────────────────────────────────────────────────

    @staticmethod
    def volume_ratio(
        volume: pd.DataFrame, window: int = 20
    ) -> pd.DataFrame:
        """Volume relative to its moving average.

        Args:
            volume: Volume DataFrame (dates × codes).
            window: MA window size (default 20).

        Returns:
            volume / volume_ma as a wide DataFrame.
        """
        vol_ma = volume.rolling(window, min_periods=5).mean()
        result = volume / vol_ma.replace(0, 1)
        result.columns = [f"{c}__vol_ratio" for c in result.columns]
        return result

    # ── High/Low ratio ────────────────────────────────────────────────────

    @staticmethod
    def high_low_ratio(
        high: pd.DataFrame, low: pd.DataFrame,
    ) -> pd.DataFrame:
        """Ratio of high to low price (intraday range proxy).

        Args:
            high: High price DataFrame.
            low: Low price DataFrame.

        Returns:
            high / low as a wide DataFrame.
        """
        result = high / low.replace(0, 1)
        result.columns = [f"{c}__high_low_ratio" for c in result.columns]
        return result

    # ── Volatility ────────────────────────────────────────────────────────

    @staticmethod
    def volatility(
        close: pd.DataFrame,
        window: int = 20,
        annual_factor: float = 252.0,
    ) -> pd.DataFrame:
        """Annualised rolling volatility from log returns.

        Args:
            close: Close price DataFrame.
            window: Rolling window size.
            annual_factor: Annualisation factor (252 for daily, 52 for weekly).

        Returns:
            Annualised volatility as a wide DataFrame.
        """
        log_ret = close.pct_change().apply(
            lambda x: x.replace([np.inf, -np.inf], np.nan)
        )
        result = (
            log_ret.rolling(window, min_periods=max(1, window // 2)).std()
            * (annual_factor ** 0.5)
        )
        result.columns = [f"{c}__volatility_{window}" for c in result.columns]
        return result

    # ── MACD ──────────────────────────────────────────────────────────────

    @staticmethod
    def macd(
        close: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> dict[str, pd.DataFrame]:
        """Moving Average Convergence Divergence.

        Returns:
            {"macd": DataFrame, "signal": DataFrame, "histogram": DataFrame}.
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
        }

    # ── Bollinger Bands ───────────────────────────────────────────────────

    @staticmethod
    def bollinger(
        close: pd.DataFrame,
        window: int = 20,
        num_std: float = 2.0,
    ) -> dict[str, pd.DataFrame]:
        """Bollinger Bands.

        Returns:
            {"middle": SMA, "upper": middle + num_std*std, "lower": middle - num_std*std}.
        """
        middle = close.rolling(window, min_periods=window).mean()
        std = close.rolling(window, min_periods=window).std()
        upper = middle + num_std * std
        lower = middle - num_std * std
        return {"middle": middle, "upper": upper, "lower": lower}

    # ── ATR ───────────────────────────────────────────────────────────────

    @staticmethod
    def atr(
        high: pd.DataFrame,
        low: pd.DataFrame,
        close: pd.DataFrame,
        period: int = 14,
    ) -> pd.DataFrame:
        """Average True Range.

        Args:
            high, low, close: OHLC DataFrames.
            period: ATR lookback period.

        Returns:
            ATR values as a wide DataFrame.
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Reshape back to wide format
        if isinstance(true_range, pd.Series):
            true_range = pd.DataFrame(true_range)
        result = true_range.rolling(period, min_periods=period).mean()
        return result

    # ── Batch compute ─────────────────────────────────────────────────────

    @staticmethod
    def compute_all(
        close: pd.DataFrame,
        volume: pd.DataFrame | None = None,
        high: pd.DataFrame | None = None,
        low: pd.DataFrame | None = None,
        *,
        preset: str = "all",
        rsi_period: int = 14,
        sma_windows: list[int] | None = None,
        ret_windows: list[int] | None = None,
        vol_window: int = 20,
    ) -> dict[str, pd.DataFrame]:
        """Batch compute multiple indicators according to a preset.

        Args:
            close, volume, high, low: OHLC panels.
            preset: One of "all", "momentum", "moving_avg", "volatility", "volume".
            rsi_period: RSI period.
            sma_windows: List of SMA windows (default [20, 60]).
            ret_windows: List of return windows (default [1, 5, 20]).
            vol_window: Volatility window.

        Returns:
            Dict of {indicator_name: DataFrame}.
        """
        wanted = set(PRESET_INDICATORS.get(preset, PRESET_INDICATORS["all"]))
        if sma_windows is None:
            sma_windows = [20, 60]
        if ret_windows is None:
            ret_windows = [1, 5, 20]

        results: dict[str, pd.DataFrame] = {}

        # RSI
        if any(k.startswith("rsi") for k in wanted):
            results[f"rsi_{rsi_period}"] = IndicatorEngine.rsi(close, rsi_period)

        # SMAs
        for w in sma_windows:
            key = f"sma_{w}"
            if key in wanted:
                results[key] = IndicatorEngine.sma(close, w)

        # Returns
        for w in ret_windows:
            key = f"ret_{w}d"
            if key in wanted:
                results[key] = IndicatorEngine.returns(close, w)

        # Volume ratio
        if "vol_ratio" in wanted and volume is not None:
            results["vol_ratio"] = IndicatorEngine.volume_ratio(volume)

        # High/Low ratio
        if "high_low_ratio" in wanted and high is not None and low is not None:
            results["high_low_ratio"] = IndicatorEngine.high_low_ratio(high, low)

        # Volatility
        vol_key = f"volatility_{vol_window}"
        if vol_key in wanted:
            results[vol_key] = IndicatorEngine.volatility(close, vol_window)

        return results
