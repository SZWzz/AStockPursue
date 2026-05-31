"""Base protocol and normalization helpers for news sources."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Source TTL configuration (seconds) ──────────────────────────────────────

SOURCE_TTL: dict[str, int] = {
    "cls": 60,                # 财联社实时电报
    "eastmoney_global": 90,   # 东财 7x24 快讯
    "eastmoney_stock": 300,   # 东财个股新闻
    "sina": 300,              # 新浪快讯
    "futu": 300,              # 富途快讯
    "ths": 300,               # 同花顺快讯
    "xueqiu": 300,            # 雪球热股
    "cninfo": 1800,           # 巨潮公告（30分钟）
    "gnews": 600,             # Google News（10分钟）
    "newsapi": 600,           # NewsAPI（10分钟）
    "web_search": 1800,       # DuckDuckGo 搜索（30分钟）
}

# ── Source metadata ─────────────────────────────────────────────────────────

SOURCE_META: dict[str, dict[str, str]] = {
    "eastmoney_stock":  {"id": "eastmoney_stock",  "label": "东财个股", "category": "stock"},
    "eastmoney_global": {"id": "eastmoney_global", "label": "东财全球", "category": "market"},
    "cls":              {"id": "cls",              "label": "财联社",   "category": "market"},
    "cninfo":           {"id": "cninfo",           "label": "巨潮公告", "category": "disclosure"},
    "sina":             {"id": "sina",             "label": "新浪财经", "category": "market"},
    "xueqiu":           {"id": "xueqiu",           "label": "雪球热股", "category": "community"},
    "futu":             {"id": "futu",             "label": "富途牛牛", "category": "market"},
    "ths":              {"id": "ths",              "label": "同花顺",   "category": "market"},
    "gnews":            {"id": "gnews",            "label": "GNews",    "category": "international"},
    "newsapi":          {"id": "newsapi",          "label": "NewsAPI",  "category": "international"},
    "web_search":       {"id": "web_search",       "label": "网页搜索", "category": "market"},
}


class BaseNewsSource:
    """Protocol for a single news data source.

    Each source must provide:
      - name: unique identifier matching SOURCE_META key
      - label: human-readable Chinese name
      - category: "stock" | "market" | "disclosure" | "community" | "international"

    Subclasses should override *at least one* of:
      - fetch_stock(symbol, limit)  → per-stock news
      - fetch_market(limit)         → market-wide news
    """

    name: str = "base"
    label: str = "未知来源"
    category: str = "market"

    def fetch_stock(self, symbol: str, limit: int = 10) -> list[dict]:
        """Fetch news for a specific stock symbol."""
        return []

    def fetch_market(self, limit: int = 10) -> list[dict]:
        """Fetch market-wide / general news."""
        return []

    def is_available(self) -> bool:
        """Check whether this source is available (dependencies installed, network ok)."""
        return True

    def ttl_seconds(self) -> int:
        """Cache TTL in seconds for this source."""
        return SOURCE_TTL.get(self.name, 300)


def normalize_article(
    raw: dict,
    source_name: str,
) -> dict | None:
    """Normalize a raw article dict from any source into the standard format.

    Returns None if the article should be skipped (e.g. empty title).

    Standard format:
        {
            "title": str,
            "url": str,
            "source": str,          # source identifier (e.g. "eastmoney_stock")
            "source_label": str,    # human-readable Chinese label (e.g. "东财个股")
            "summary": str,         # snippet / first 200 chars
            "published_at": str,    # ISO 8601
        }
    """
    title = (raw.get("title") or raw.get("name") or raw.get("content", "")).strip()
    if not title:
        return None

    # Truncate long titles
    if len(title) > 500:
        title = title[:500]

    summary = (raw.get("summary") or raw.get("content") or raw.get("snippet") or raw.get("description") or "").strip()
    if len(summary) > 500:
        summary = summary[:500]

    url = raw.get("url") or raw.get("link") or ""

    published_at = raw.get("published_at") or raw.get("time") or raw.get("date") or raw.get("publishedAt") or ""
    if published_at:
        published_at = _normalize_datetime(published_at)

    meta = SOURCE_META.get(source_name, {"id": source_name, "label": source_name})

    return {
        "title": title,
        "url": url,
        "source": source_name,
        "source_label": meta.get("label", source_name),
        "summary": summary[:200] if summary else "",
        "published_at": published_at,
    }


def _normalize_datetime(dt_str: str) -> str:
    """Attempt to normalize various datetime formats to ISO 8601."""
    if not dt_str:
        return ""

    # Already ISO-ish?
    if "T" in dt_str:
        return dt_str.replace("Z", "+00:00")[:25]

    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str.strip()[: len(fmt)], fmt)
            return dt.isoformat()
        except (ValueError, IndexError):
            continue

    # If it looks like a unix timestamp
    try:
        ts = float(dt_str)
        if ts > 1e9:  # seconds
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:  # milliseconds
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, OverflowError):
        pass

    return dt_str


def deduplicate_by_url(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL."""
    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        url = a.get("url", "")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(a)
    return unique


def deduplicate_by_title_similarity(articles: list[dict], threshold: float = 0.85) -> list[dict]:
    """Remove near-duplicate articles by title similarity (difflib)."""
    from difflib import SequenceMatcher

    unique: list[dict] = []
    for a in articles:
        is_dup = False
        for u in unique:
            ratio = SequenceMatcher(None, a.get("title", ""), u.get("title", "")).ratio()
            if ratio > threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(a)
    return unique
