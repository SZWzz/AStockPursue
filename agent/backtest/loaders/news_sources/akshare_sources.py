"""akshare-based news sources.

4 sources sharing the same akshare dependency (already in pyproject.toml):
  - SinaFinanceSource  — stock_info_global_sina / stock_info_broker_sina
  - XueqiuSource       — stock_hot_follow/tweet/deal_xq (community rankings)
  - FutuSource         — stock_info_global_futu
  - THSSource          — stock_info_global_ths

Each source gracefully handles akshare not being installed.
"""

from __future__ import annotations

import logging

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)


# ── Helper ──────────────────────────────────────────────────────────────────


def _ak_available() -> bool:
    try:
        import akshare  # noqa: F401
        return True
    except ImportError:
        return False


def _safe_fetch(fn, *args, **kwargs):
    """Call an akshare function safely, returning [] on failure."""
    if not _ak_available():
        return []
    try:
        result = fn(*args, **kwargs)
        if result is None or (hasattr(result, "empty") and result.empty):
            return []
        if hasattr(result, "to_dict"):
            return result.to_dict(orient="records")
        return list(result) if isinstance(result, (list, tuple)) else []
    except Exception as e:
        logger.debug("akshare fetch failed (%s): %s", getattr(fn, "__name__", str(fn)), e)
        return []


# ── SinaFinanceSource ───────────────────────────────────────────────────────


class SinaFinanceSource(BaseNewsSource):
    """新浪财经全球快讯."""

    name = "sina"
    label = "新浪财经"
    category = "market"

    def fetch_market(self, limit: int = 20) -> list[dict]:
        raw = _safe_fetch(self._fetch_global)
        raw += _safe_fetch(self._fetch_broker)
        return self._normalize(raw)[:limit]

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        raw = _safe_fetch(self._fetch_global)
        normalized = self._normalize(raw)
        # Filter by symbol keyword
        filtered: list[dict] = []
        for a in normalized:
            text = f"{a.get('title', '')} {a.get('summary', '')}"
            if symbol.replace(".SZ", "").replace(".SH", "") in text:
                filtered.append(a)
        return filtered[:limit]

    @staticmethod
    def _fetch_global():
        import akshare as ak
        df = ak.stock_info_global_sina()
        if df is None or df.empty:
            return []
        return [
            {"title": row.get("内容", ""), "url": "", "time": str(row.get("时间", ""))}
            for _, row in df.iterrows()
        ]

    @staticmethod
    def _fetch_broker():
        import akshare as ak
        df = ak.stock_info_broker_sina()
        if df is None or df.empty:
            return []
        return [
            {"title": row.get("内容", ""), "url": "", "time": str(row.get("时间", ""))}
            for _, row in df.iterrows()
        ]

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles


# ── XueqiuSource ────────────────────────────────────────────────────────────


class XueqiuSource(BaseNewsSource):
    """雪球热股排行 — 关注/讨论/交易三大排行榜."""

    name = "xueqiu"
    label = "雪球热股"
    category = "community"

    def fetch_market(self, limit: int = 20) -> list[dict]:
        raw: list[dict] = []
        raw += _safe_fetch(self._fetch_follow, "最热门")
        raw += _safe_fetch(self._fetch_tweet, "最热门")
        raw += _safe_fetch(self._fetch_deal, "最热门")
        return self._normalize(raw)[:limit]

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        # Xueqiu doesn't have per-stock news API, return empty
        return []

    @staticmethod
    def _fetch_follow(sort: str = "最热门"):
        import akshare as ak
        df = ak.stock_hot_follow_xq(symbol=sort)
        if df is None or df.empty:
            return []
        return [
            {
                "title": f"{row.get('股票简称', '')}({row.get('股票代码', '')}) 关注度排行",
                "url": "",
                "summary": f"关注数: {row.get('关注', '')} 最新价: {row.get('最新价', '')}",
                "time": "",
            }
            for _, row in df.iterrows()
        ]

    @staticmethod
    def _fetch_tweet(sort: str = "最热门"):
        import akshare as ak
        df = ak.stock_hot_tweet_xq(symbol=sort)
        if df is None or df.empty:
            return []
        return [
            {
                "title": f"{row.get('股票简称', '')}({row.get('股票代码', '')}) 讨论热度",
                "url": "",
                "summary": f"讨论数: {row.get('关注', '')} 最新价: {row.get('最新价', '')}",
                "time": "",
            }
            for _, row in df.iterrows()
        ]

    @staticmethod
    def _fetch_deal(sort: str = "最热门"):
        import akshare as ak
        df = ak.stock_hot_deal_xq(symbol=sort)
        if df is None or df.empty:
            return []
        return [
            {
                "title": f"{row.get('股票简称', '')}({row.get('股票代码', '')}) 交易热度",
                "url": "",
                "summary": f"交易分享: {row.get('关注', '')} 最新价: {row.get('最新价', '')}",
                "time": "",
            }
            for _, row in df.iterrows()
        ]

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles


# ── FutuSource ──────────────────────────────────────────────────────────────


class FutuSource(BaseNewsSource):
    """富途牛牛快讯."""

    name = "futu"
    label = "富途牛牛"
    category = "market"

    def fetch_market(self, limit: int = 20) -> list[dict]:
        raw = _safe_fetch(self._fetch)
        return self._normalize(raw)[:limit]

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        raw = _safe_fetch(self._fetch)
        normalized = self._normalize(raw)
        filtered: list[dict] = []
        for a in normalized:
            text = f"{a.get('title', '')} {a.get('summary', '')}"
            if symbol.replace(".SZ", "").replace(".SH", "") in text:
                filtered.append(a)
        return filtered[:limit]

    @staticmethod
    def _fetch():
        import akshare as ak
        df = ak.stock_info_global_futu()
        if df is None or df.empty:
            return []
        return [
            {
                "title": row.get("标题", ""),
                "url": row.get("链接", ""),
                "summary": (row.get("内容", "") or "")[:200],
                "time": str(row.get("发布时间", "")),
            }
            for _, row in df.iterrows()
        ]

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles


# ── THSSource ───────────────────────────────────────────────────────────────


class THSSource(BaseNewsSource):
    """同花顺快讯."""

    name = "ths"
    label = "同花顺"
    category = "market"

    def fetch_market(self, limit: int = 20) -> list[dict]:
        raw = _safe_fetch(self._fetch)
        return self._normalize(raw)[:limit]

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        raw = _safe_fetch(self._fetch)
        normalized = self._normalize(raw)
        filtered: list[dict] = []
        for a in normalized:
            text = f"{a.get('title', '')} {a.get('summary', '')}"
            if symbol.replace(".SZ", "").replace(".SH", "") in text:
                filtered.append(a)
        return filtered[:limit]

    @staticmethod
    def _fetch():
        import akshare as ak
        df = ak.stock_info_global_ths()
        if df is None or df.empty:
            return []
        return [
            {
                "title": row.get("标题", ""),
                "url": row.get("链接", ""),
                "summary": (row.get("内容", "") or "")[:200],
                "time": str(row.get("发布时间", "")),
            }
            for _, row in df.iterrows()
        ]

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles
