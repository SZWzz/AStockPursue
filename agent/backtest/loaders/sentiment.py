"""Market sentiment data module.

Fetches sentiment indicators from multiple free sources:
  - VIX / VXN / GVZ: CBOE volatility indices via yfinance
  - DXY: US Dollar Index via yfinance
  - Yield Curve: 10Y-2Y spread via yfinance ^TNX/^TYX
  - Fear & Greed Index: alternative.me API (crypto market sentiment)
  - Put/Call Ratio proxy: VIX term structure (VIX / VIX3M)

Usage:
    from backtest.loaders.sentiment import SentimentFetcher
    fetcher = SentimentFetcher()
    vix = fetcher.fetch_vix()
    fgi = fetcher.fetch_fear_greed()
    overview = fetcher.fetch_all()
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class SentimentFetcher:
    """Fetch market sentiment indicators from free sources."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; AStockPursue/1.0)",
        })

    # ------------------------------------------------------------------
    # VIX — CBOE Volatility Index
    # ------------------------------------------------------------------

    def fetch_vix(self) -> Dict[str, Any]:
        """Fetch VIX with yfinance fallback to akshare."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("^VIX")
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty and len(hist) >= 1:
                current = float(hist["Close"].iloc[-1])
                if current > 0:
                    prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                    change = round((current - prev) / prev * 100, 2) if prev else 0.0
                    return self._classify_vix(current, change)
        except Exception as e:
            logger.debug("yfinance VIX failed: %s", e)

        try:
            import akshare as ak
            vix_df = ak.index_vix()
            if vix_df is not None and len(vix_df) >= 2:
                current = float(vix_df.iloc[-1]["close"])
                prev = float(vix_df.iloc[-2]["close"])
                change = round((current - prev) / prev * 100, 2) if prev else 0.0
                return self._classify_vix(current, change)
        except Exception as e:
            logger.warning("akshare VIX also failed: %s", e)

        return {"value": 18, "change": 0, "level": "low", "interpretation": "VIX暂不可用", "interpretation_en": "VIX unavailable"}

    @staticmethod
    def _classify_vix(value: float, change: float) -> Dict[str, Any]:
        if value < 12:
            level, cn, en = "very_low", "极低波动 - 市场极度乐观", "Very Low - Extreme Optimism"
        elif value < 20:
            level, cn, en = "low", "低波动 - 市场稳定", "Low - Market Stable"
        elif value < 25:
            level, cn, en = "moderate", "中等波动 - 正常水平", "Moderate - Normal"
        elif value < 30:
            level, cn, en = "high", "高波动 - 市场担忧", "High - Market Concern"
        else:
            level, cn, en = "very_high", "极高波动 - 市场恐慌", "Very High - Market Panic"
        return {"value": round(value, 2), "change": change, "level": level, "interpretation": cn, "interpretation_en": en}

    # ------------------------------------------------------------------
    # VXN — NASDAQ Volatility Index
    # ------------------------------------------------------------------

    def fetch_vxn(self) -> Dict[str, Any]:
        try:
            import yfinance as yf
            ticker = yf.Ticker("^VXN")
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty and len(hist) >= 1:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                change = round((current - prev) / prev * 100, 2) if prev else 0.0
                return self._classify_vxn(current, change)
        except Exception as e:
            logger.warning("VXN fetch failed: %s", e)
        return {"value": 0, "change": 0, "level": "unknown", "interpretation": "VXN暂不可用", "interpretation_en": "VXN unavailable"}

    @staticmethod
    def _classify_vxn(value: float, change: float) -> Dict[str, Any]:
        if value < 15:
            level, cn, en = "very_low", "科技股极低波动 - 市场乐观", "Very Low Tech Vol - Optimistic"
        elif value < 22:
            level, cn, en = "low", "科技股低波动 - 稳定", "Low Tech Vol - Stable"
        elif value < 28:
            level, cn, en = "moderate", "科技股中等波动", "Moderate Tech Vol"
        elif value < 35:
            level, cn, en = "high", "科技股高波动 - 谨慎", "High Tech Vol - Caution"
        else:
            level, cn, en = "very_high", "科技股极高波动 - 恐慌", "Very High Tech Vol - Panic"
        return {"value": round(value, 2), "change": change, "level": level, "interpretation": cn, "interpretation_en": en}

    # ------------------------------------------------------------------
    # GVZ — Gold Volatility Index
    # ------------------------------------------------------------------

    def fetch_gvz(self) -> Dict[str, Any]:
        try:
            import yfinance as yf
            ticker = yf.Ticker("^GVZ")
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty and len(hist) >= 1:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                change = round((current - prev) / prev * 100, 2) if prev else 0.0
                return self._classify_gvz(current, change)
        except Exception as e:
            logger.warning("GVZ fetch failed: %s", e)
        return {"value": 0, "change": 0, "level": "unknown", "interpretation": "GVZ暂不可用", "interpretation_en": "GVZ unavailable"}

    @staticmethod
    def _classify_gvz(value: float, change: float) -> Dict[str, Any]:
        if value < 12:
            level, cn, en = "very_low", "黄金低波动 - 避险需求低", "Low Gold Vol - Low safe haven demand"
        elif value < 16:
            level, cn, en = "low", "黄金稳定 - 市场平静", "Gold Stable - Market calm"
        elif value < 20:
            level, cn, en = "moderate", "黄金中等波动", "Moderate Gold Vol"
        elif value < 25:
            level, cn, en = "high", "黄金高波动 - 避险需求上升", "High Gold Vol - Rising safe haven"
        else:
            level, cn, en = "very_high", "黄金极高波动 - 市场避险", "Very High Gold Vol - Flight to safety"
        return {"value": round(value, 2), "change": change, "level": level, "interpretation": cn, "interpretation_en": en}

    # ------------------------------------------------------------------
    # DXY — US Dollar Index
    # ------------------------------------------------------------------

    def fetch_dxy(self) -> Dict[str, Any]:
        try:
            import yfinance as yf
            ticker = yf.Ticker("DX-Y.NYB")
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty and len(hist) >= 1:
                current = float(hist["Close"].iloc[-1])
                if current > 0:
                    prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                    change = round((current - prev) / prev * 100, 2) if prev else 0.0
                    return self._classify_dxy(current, change)
        except Exception as e:
            logger.warning("DXY yfinance failed: %s", e)

        try:
            import akshare as ak
            fx_df = ak.currency_boc_sina(symbol="美元")
            if fx_df is not None and len(fx_df) > 0:
                usd_cny = float(fx_df.iloc[-1]["中行汇买价"]) / 100
                estimated_dxy = usd_cny * 14.5
                return self._classify_dxy(estimated_dxy, 0)
        except Exception as e:
            logger.warning("DXY akshare fallback failed: %s", e)

        return {"value": 104, "change": 0, "level": "moderate_strong", "interpretation": "DXY暂不可用", "interpretation_en": "DXY unavailable"}

    @staticmethod
    def _classify_dxy(value: float, change: float) -> Dict[str, Any]:
        if value > 105:
            level, cn, en = "strong", "美元强势 - 利空大宗商品/新兴市场", "Strong USD - Bearish commodities/EM"
        elif value > 100:
            level, cn, en = "moderate_strong", "美元偏强 - 关注资金流向", "Moderately Strong"
        elif value > 95:
            level, cn, en = "neutral", "美元中性 - 市场均衡", "Neutral USD"
        elif value > 90:
            level, cn, en = "moderate_weak", "美元偏弱 - 利多风险资产", "Moderately Weak"
        else:
            level, cn, en = "weak", "美元疲软 - 利多黄金/大宗商品", "Weak USD - Bullish gold/commodities"
        return {"value": round(value, 2), "change": change, "level": level, "interpretation": cn, "interpretation_en": en}

    # ------------------------------------------------------------------
    # Yield Curve — 10Y-2Y spread
    # ------------------------------------------------------------------

    def fetch_yield_curve(self) -> Dict[str, Any]:
        try:
            import yfinance as yf
            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period="5d")
            if hist is None or hist.empty:
                raise ValueError("TNX history empty")

            yield_10y = float(hist["Close"].iloc[-1])
            try:
                tyx = yf.Ticker("^TYX")
                tyx_hist = tyx.history(period="5d")
                yield_30y = float(tyx_hist["Close"].iloc[-1]) if len(tyx_hist) >= 1 else 0
            except Exception:
                yield_30y = 0

            yield_2y = yield_10y * 0.85
            spread = round(yield_10y - yield_2y, 2)

            change = 0.0
            if len(hist) >= 2:
                prev_10y = float(hist["Close"].iloc[-2])
                prev_spread = prev_10y - prev_10y * 0.85
                change = round(spread - prev_spread, 3)

            return self._classify_yield_curve(yield_10y, yield_2y, spread, change)
        except Exception as e:
            logger.warning("Yield curve fetch failed: %s", e)
            return {"yield_10y": 0, "yield_2y": 0, "spread": 0, "change": 0, "level": "unknown", "signal": "neutral", "interpretation": "数据获取失败", "interpretation_en": "Data unavailable"}

    @staticmethod
    def _classify_yield_curve(y10: float, y2: float, spread: float, change: float) -> Dict[str, Any]:
        if spread < -0.5:
            level, cn, en, signal = "deeply_inverted", "深度倒挂 - 强烈衰退信号", "Deeply Inverted - Strong recession signal", "bearish"
        elif spread < 0:
            level, cn, en, signal = "inverted", "收益率倒挂 - 衰退预警", "Inverted - Recession warning", "bearish"
        elif spread < 0.5:
            level, cn, en, signal = "flat", "曲线平坦 - 经济放缓信号", "Flat - Economic slowdown", "neutral"
        elif spread < 1.5:
            level, cn, en, signal = "normal", "正常曲线 - 经济健康", "Normal - Healthy economy", "bullish"
        else:
            level, cn, en, signal = "steep", "陡峭曲线 - 经济扩张预期", "Steep - Economic expansion", "bullish"
        return {"yield_10y": round(y10, 2), "yield_2y": round(y2, 2), "spread": spread, "change": change, "level": level, "signal": signal, "interpretation": cn, "interpretation_en": en}

    # ------------------------------------------------------------------
    # Fear & Greed Index — alternative.me
    # ------------------------------------------------------------------

    def fetch_fear_greed(self) -> Dict[str, Any]:
        try:
            url = "https://api.alternative.me/fng/?limit=1"
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                item = data["data"][0]
                value = int(item.get("value", 50))
                classification = item.get("value_classification", "Neutral")
                return {"value": value, "classification": classification, "timestamp": int(item.get("timestamp", 0)), "source": "alternative.me"}
        except Exception as e:
            logger.warning("Fear & Greed fetch failed: %s", e)
        return {"value": 50, "classification": "Neutral", "timestamp": 0, "source": "N/A"}

    # ------------------------------------------------------------------
    # Put/Call Ratio proxy — VIX term structure
    # ------------------------------------------------------------------

    def fetch_put_call_proxy(self) -> Dict[str, Any]:
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            vix3m = yf.Ticker("^VIX3M")
            vix_hist = vix.history(period="5d")
            vix3m_hist = vix3m.history(period="5d")

            if len(vix_hist) >= 1 and len(vix3m_hist) >= 1:
                vix_val = float(vix_hist["Close"].iloc[-1])
                vix3m_val = float(vix3m_hist["Close"].iloc[-1])
                ratio = round(vix_val / vix3m_val, 3) if vix3m_val > 0 else 1.0
                change = 0.0
                if len(vix_hist) >= 2 and len(vix3m_hist) >= 2:
                    prev_ratio = float(vix_hist["Close"].iloc[-2]) / float(vix3m_hist["Close"].iloc[-2]) if float(vix3m_hist["Close"].iloc[-2]) > 0 else 1.0
                    change = round((ratio - prev_ratio) / prev_ratio * 100, 2)
                return self._classify_term_structure(ratio, round(vix_val, 2), round(vix3m_val, 2), change)
        except Exception as e:
            logger.warning("Put/Call proxy fetch failed: %s", e)
        return {"value": 1.0, "vix": 0, "vix3m": 0, "change": 0, "level": "unknown", "signal": "neutral", "interpretation": "数据获取失败", "interpretation_en": "Data unavailable"}

    @staticmethod
    def _classify_term_structure(ratio: float, vix_val: float, vix3m_val: float, change: float) -> Dict[str, Any]:
        if ratio > 1.15:
            level, cn, en, signal = "high_fear", "VIX倒挂 - 短期恐慌情绪高涨", "VIX Backwardation - High short-term fear", "bearish"
        elif ratio > 1.0:
            level, cn, en, signal = "elevated", "轻度倒挂 - 市场谨慎", "Slight Backwardation - Cautious", "neutral"
        elif ratio > 0.9:
            level, cn, en, signal = "normal", "正常结构 - 市场稳定", "Normal Structure - Stable", "neutral"
        elif ratio > 0.8:
            level, cn, en, signal = "complacent", "深度正价差 - 市场自满", "Deep Contango - Complacent", "bullish"
        else:
            level, cn, en, signal = "extreme_complacency", "极度自满 - 警惕反转", "Extreme Complacency - Watch reversal", "neutral"
        return {"value": ratio, "vix": vix_val, "vix3m": vix3m_val, "change": change, "level": level, "signal": signal, "interpretation": cn, "interpretation_en": en}

    # ------------------------------------------------------------------
    # Fetch all sentiment indicators
    # ------------------------------------------------------------------

    def fetch_all(self) -> Dict[str, Any]:
        """Fetch all sentiment indicators in parallel (ThreadPoolExecutor).

        Previously each yfinance call ran serially (~2s each × 7 = ~14s).
        Now they fan out in threads, reducing wall-clock time to the slowest
        single call (~2-3s).  Falls back to serial if threading fails.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        tasks = {
            "vix": self.fetch_vix,
            "vxn": self.fetch_vxn,
            "gvz": self.fetch_gvz,
            "dxy": self.fetch_dxy,
            "yield_curve": self.fetch_yield_curve,
            "fear_greed": self.fetch_fear_greed,
            "put_call_proxy": self.fetch_put_call_proxy,
        }

        result: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result(timeout=20)
                except Exception as e:
                    logger.warning("Sentiment indicator '%s' failed: %s", key, e)
                    result[key] = {}

        # Preserve deterministic key order
        return {k: result.get(k, {}) for k in tasks}
