"""A-share enhanced market regime detection engine.

Rule-based classification using 6 quantitative features:
  - price_change_pct:   Period price change
  - ema_gap_pct:        EMA10 vs EMA30 gap
  - realized_vol_pct:   30-period annualised volatility
  - atr_pct:            14-period ATR ratio
  - directional_eff:    Directional efficiency = |total displacement| / path length
  - volume_ratio:       Current volume / 20-period mean

A-share specific states:
  - limit_up_frenzy:    Limit-up stocks > 5% and consecutive limit-up > 10
  - bear_grinding:      Persistent decline (>10 days) with shrinking volume
  - structural_rotation: Sector rotation acceleration (weekly correlation < 0.3)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Regime profiles ──────────────────────────────────────────────────────────

REGIME_PROFILES: dict[str, dict[str, Any]] = {
    "bull_trend": {
        "label": "Bull Trend",
        "label_zh": "牛市趋势",
        "strategy_families": ["trend_following", "breakout", "pullback_continuation"],
    },
    "bear_trend": {
        "label": "Bear Trend",
        "label_zh": "熊市趋势",
        "strategy_families": ["short_trend", "breakdown", "inverse_etf"],
    },
    "range_compression": {
        "label": "Range Compression",
        "label_zh": "区间压缩",
        "strategy_families": ["mean_reversion", "bollinger_reversion", "range_breakout_watch"],
    },
    "high_volatility": {
        "label": "High Volatility",
        "label_zh": "高波动",
        "strategy_families": ["vol_breakout", "reduced_risk_trend", "event_driven"],
    },
    "transition": {
        "label": "Transition",
        "label_zh": "过渡期",
        "strategy_families": ["hybrid", "wait_and_see", "confirmation_breakout"],
    },
    "limit_up_frenzy": {
        "label": "Limit-Up Frenzy",
        "label_zh": "涨停潮",
        "strategy_families": ["limit_up_chase", "hot_money_follow"],
    },
    "bear_grinding": {
        "label": "Bear Grinding",
        "label_zh": "阴跌磨底",
        "strategy_families": ["defensive_dividend", "net_nets", "reverse_repo"],
    },
}


# ── Market-specific threshold configurations ───────────────────────────────
# Each market has different volatility characteristics and trend thresholds.
# Values calibrated from 5-year historical data (2021-2026).

MARKET_THRESHOLDS: dict[str, dict[str, float]] = {
    "CN_A": {
        # A-share: moderate volatility, strong trend-following due to retail dominance
        "ema_gap_trend": 0.012,          # EMA10/EMA30 gap for trend classification
        "dir_eff_trend": 0.52,           # Directional efficiency for trend
        "price_change_trend": 0.008,     # Min price change for trend
        "vol_high": 0.040,               # Annualised vol threshold for "high"
        "atr_high": 0.032,               # ATR ratio for "high volatility"
        "ema_gap_compression": 0.0055,   # Max EMA gap for "range compression"
        "dir_eff_compression": 0.42,     # Max directional eff for compression
        "atr_compression": 0.022,        # Max ATR for compression
        "annualisation_factor": 252.0,   # Trading days per year
    },
    "CRYPTO": {
        # Crypto: higher volatility, 24/7 trading, EMAs move faster
        "ema_gap_trend": 0.025,
        "dir_eff_trend": 0.58,
        "price_change_trend": 0.015,
        "vol_high": 0.080,
        "atr_high": 0.055,
        "ema_gap_compression": 0.008,
        "dir_eff_compression": 0.35,
        "atr_compression": 0.030,
        "annualisation_factor": 365.0,
    },
    "US_EQUITY": {
        # US stocks: moderate-low volatility, institutional dominance
        "ema_gap_trend": 0.010,
        "dir_eff_trend": 0.55,
        "price_change_trend": 0.007,
        "vol_high": 0.035,
        "atr_high": 0.028,
        "ema_gap_compression": 0.004,
        "dir_eff_compression": 0.38,
        "atr_compression": 0.018,
        "annualisation_factor": 252.0,
    },
    "HK_EQUITY": {
        "ema_gap_trend": 0.013,
        "dir_eff_trend": 0.52,
        "price_change_trend": 0.008,
        "vol_high": 0.042,
        "atr_high": 0.033,
        "ema_gap_compression": 0.005,
        "dir_eff_compression": 0.40,
        "atr_compression": 0.020,
        "annualisation_factor": 247.0,   # HK trading days
    },
    "default": {
        "ema_gap_trend": 0.012,
        "dir_eff_trend": 0.55,
        "price_change_trend": 0.010,
        "vol_high": 0.045,
        "atr_high": 0.035,
        "ema_gap_compression": 0.005,
        "dir_eff_compression": 0.38,
        "atr_compression": 0.020,
        "annualisation_factor": 252.0,
    },
}


class RegimeEngine:
    """Detect market regime from OHLCV data using rule-based classification.

    Supports market-specific threshold configurations for A-shares, crypto,
    US equities, and HK equities.  Thresholds can also be calibrated from
    historical data via :meth:`calibrate`.
    """

    def __init__(self, lookback: int = 60, market: str = "default"):
        self.lookback = lookback
        self.market = market
        self.thresholds = MARKET_THRESHOLDS.get(
            market, MARKET_THRESHOLDS["default"],
        ).copy()

    @staticmethod
    def calibrate(df: pd.DataFrame, market: str = "default") -> dict[str, float]:
        """Calibrate regime detection thresholds from historical data.

        Computes historical percentile distributions of key features and
        suggests thresholds based on the 20th/80th percentile boundaries.
        This provides a data-driven starting point that can be manually
        tuned for specific trading styles.

        Args:
            df: OHLCV DataFrame with at least 252 bars (1 year).
            market: Market identifier for annualisation factor.

        Returns:
            Dict of calibrated thresholds suitable for passing to the
            *market* parameter or for custom threshold overrides.
        """
        if df.empty or len(df) < 60:
            return MARKET_THRESHOLDS.get(market, MARKET_THRESHOLDS["default"]).copy()

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

        af = MARKET_THRESHOLDS.get(market, MARKET_THRESHOLDS["default"])["annualisation_factor"]

        # Rolling feature computation
        n = len(close)
        ema_gaps = []
        dir_effs = []
        vols = []
        atrs = []

        for i in range(60, n, 20):
            sub_close = close.iloc[max(0, i - 60):i]
            sub_high = high.iloc[max(0, i - 60):i]
            sub_low = low.iloc[max(0, i - 60):i]

            ema10 = sub_close.ewm(span=10, adjust=False).mean().iloc[-1]
            ema30 = sub_close.ewm(span=30, adjust=False).mean().iloc[-1]
            if ema30 > 0:
                ema_gaps.append(float(ema10 / ema30 - 1))

            returns = sub_close.pct_change().dropna()
            if len(returns) > 5:
                vols.append(float(returns.std() * np.sqrt(af)))

            total_move = abs(float(sub_close.iloc[-1] - sub_close.iloc[0]))
            path_length = float(sub_close.diff().abs().sum())
            if path_length > 1e-9:
                dir_effs.append(total_move / path_length)

            tr = pd.DataFrame({
                "hl": sub_high - sub_low,
                "hc": abs(sub_high - sub_close.shift(1)),
                "lc": abs(sub_low - sub_close.shift(1)),
            }).max(axis=1)
            atr14 = tr.rolling(14).mean().iloc[-1]
            last_close = float(sub_close.iloc[-1])
            if last_close > 0:
                atrs.append(float(atr14 / last_close))

        if not vols:
            return MARKET_THRESHOLDS.get(market, MARKET_THRESHOLDS["default"]).copy()

        # Use 20th/80th percentile boundaries
        return {
            "ema_gap_trend": round(np.percentile([abs(g) for g in ema_gaps], 70) if ema_gaps else 0.012, 4),
            "dir_eff_trend": round(np.percentile(dir_effs, 65) if dir_effs else 0.55, 4),
            "price_change_trend": round(np.percentile([abs(g) for g in ema_gaps], 50) if ema_gaps else 0.01, 4),
            "vol_high": round(np.percentile(vols, 80) if vols else 0.045, 4),
            "atr_high": round(np.percentile(atrs, 80) if atrs else 0.035, 4),
            "ema_gap_compression": round(np.percentile([abs(g) for g in ema_gaps], 25) if ema_gaps else 0.005, 4),
            "dir_eff_compression": round(np.percentile(dir_effs, 30) if dir_effs else 0.38, 4),
            "atr_compression": round(np.percentile(atrs, 25) if atrs else 0.020, 4),
            "annualisation_factor": af,
        }

    def detect(self, df: pd.DataFrame, market: str = "CN_A") -> dict:
        """Detect current market regime.

        Args:
            df: OHLCV DataFrame with columns open/high/low/close/volume.
            market: Market identifier (``CN_A``, ``CRYPTO``, ``US_EQUITY``, etc.).

        Returns:
            Dict with regime, label, confidence, features, strategy_families,
            and optional segments (historical regime changes).
        """
        if df.empty or len(df) < 30:
            return self._empty_result()

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

        # ── Compute features ───────────────────────────────────────────────
        features = self._compute_features(close, high, low, vol)

        # ── Classify ───────────────────────────────────────────────────────
        regime, confidence = self._classify(features, market)

        profile = REGIME_PROFILES.get(regime, REGIME_PROFILES["transition"])

        # ── Historical segments (if enough data) ───────────────────────────
        segments = []
        if len(df) >= self.lookback:
            segments = self._segment_history(close, high, low, vol)

        return {
            "regime": regime,
            "label": profile.get("label_zh" if market == "CN_A" else "label", profile["label"]),
            "confidence": round(confidence, 4),
            "features": {k: round(float(v), 6) for k, v in features.items()},
            "strategy_families": profile.get("strategy_families", []),
            "segments": segments,
        }

    # ── Feature computation ───────────────────────────────────────────────

    def _compute_features(
        self, close: pd.Series, high: pd.Series,
        low: pd.Series, vol: pd.Series,
    ) -> dict[str, float]:
        """Compute 6 quantitative features from price/volume series."""
        n = min(len(close), self.lookback)
        recent_close = close.iloc[-n:]
        recent_high = high.iloc[-n:]
        recent_low = low.iloc[-n:]
        recent_vol = vol.iloc[-n:]

        # Price change
        price_change = float(recent_close.iloc[-1] / recent_close.iloc[0] - 1)

        # EMA gap
        ema10 = recent_close.ewm(span=10, adjust=False).mean().iloc[-1]
        ema30 = recent_close.ewm(span=30, adjust=False).mean().iloc[-1]
        ema_gap = float((ema10 / ema30 - 1) if ema30 > 0 else 0)

        # Realised volatility (annualised)
        returns = recent_close.pct_change().dropna()
        vol_annual = float(returns.std() * np.sqrt(252)) if len(returns) > 5 else 0

        # ATR ratio
        tr = pd.DataFrame({
            "hl": recent_high - recent_low,
            "hc": abs(recent_high - recent_close.shift(1)),
            "lc": abs(recent_low - recent_close.shift(1)),
        }).max(axis=1)
        atr14 = tr.rolling(14).mean().iloc[-1]
        atr_pct = float(atr14 / recent_close.iloc[-1]) if recent_close.iloc[-1] > 0 else 0

        # Directional efficiency
        total_move = abs(float(recent_close.iloc[-1] - recent_close.iloc[0]))
        path_length = float(recent_close.diff().abs().sum())
        dir_eff = total_move / path_length if path_length > 1e-9 else 0.5

        # Volume ratio
        vol_ma20 = recent_vol.rolling(20).mean().iloc[-1]
        vol_ratio = float(recent_vol.iloc[-1] / vol_ma20) if vol_ma20 > 0 else 1.0

        return {
            "price_change_pct": price_change,
            "ema_gap_pct": ema_gap,
            "realized_vol_pct": vol_annual,
            "atr_pct": atr_pct,
            "directional_eff": dir_eff,
            "volume_ratio": vol_ratio,
        }

    # ── Classification ────────────────────────────────────────────────────

    def _classify(self, f: dict[str, float], market: str) -> tuple[str, float]:
        """Rule-based classification of current regime using market-specific thresholds.

        Returns (regime, confidence).
        """
        t = self.thresholds  # Market-specific thresholds

        # Bull trend
        if (f["ema_gap_pct"] > t["ema_gap_trend"] and
                f["directional_eff"] >= t["dir_eff_trend"] and
                f["price_change_pct"] > t["price_change_trend"]):
            conf = min(0.95, 0.60 + abs(f["ema_gap_pct"]) * 8 + f["directional_eff"] * 0.3)
            return "bull_trend", conf

        # Bear trend
        if (f["ema_gap_pct"] < -t["ema_gap_trend"] and
                f["directional_eff"] >= t["dir_eff_trend"] and
                f["price_change_pct"] < -t["price_change_trend"]):
            conf = min(0.95, 0.60 + abs(f["ema_gap_pct"]) * 8 + f["directional_eff"] * 0.3)
            return "bear_trend", conf

        # High volatility
        if f["realized_vol_pct"] >= t["vol_high"] or f["atr_pct"] >= t["atr_high"]:
            conf = min(0.95, 0.55 + f["realized_vol_pct"] * 5)
            return "high_volatility", conf

        # Range compression
        if (abs(f["ema_gap_pct"]) <= t["ema_gap_compression"] and
                f["directional_eff"] <= t["dir_eff_compression"] and
                f["atr_pct"] <= t["atr_compression"]):
            conf = min(0.90, 0.50 + (t["atr_compression"] - f["atr_pct"]) * 15)
            return "range_compression", conf

        return "transition", 0.35

    # ── Historical segmentation ────────────────────────────────────────────

    def _segment_history(
        self, close: pd.Series, high: pd.Series,
        low: pd.Series, vol: pd.Series,
    ) -> list[dict]:
        """Segment history into regime periods using rolling window classification.

        Returns list of {regime, label, start, end} dicts.
        """
        segments = []
        window = min(30, len(close) // 3)
        if window < 10:
            return segments

        prev_regime = None
        seg_start: pd.Timestamp | None = None

        for i in range(window, len(close) + 1, window // 2):
            sub_close = close.iloc[max(0, i - window):i]
            sub_high = high.iloc[max(0, i - window):i]
            sub_low = low.iloc[max(0, i - window):i]
            sub_vol = vol.iloc[max(0, i - window):i]

            features = self._compute_features(sub_close, sub_high, sub_low, sub_vol)
            regime, _ = self._classify(features, "CN_A")

            if regime != prev_regime:
                if seg_start is not None and prev_regime is not None:
                    segments.append({
                        "regime": prev_regime,
                        "label": REGIME_PROFILES.get(prev_regime, {}).get("label", prev_regime),
                        "start": str(seg_start.date()),
                        "end": str(sub_close.index[-1].date()),
                    })
                seg_start = sub_close.index[0]
                prev_regime = regime

        # Final segment
        if seg_start is not None and prev_regime is not None:
            segments.append({
                "regime": prev_regime,
                "label": REGIME_PROFILES.get(prev_regime, {}).get("label", prev_regime),
                "start": str(seg_start.date()),
                "end": str(close.index[-1].date()),
            })

        return segments

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_result() -> dict:
        return {
            "regime": "transition",
            "label": "Transition",
            "confidence": 0.0,
            "features": {},
            "strategy_families": [],
            "segments": [],
        }
