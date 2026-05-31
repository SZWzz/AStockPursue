"""CLS Telegraph (财联社电报) — direct HTTP API (from 01.md).

Source: www.cls.cn/nodeapi/telegraphList
Returns: real-time market telegraph/news with title, content, time
"""

from __future__ import annotations

import logging

import requests

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class CLSTelegraphSource(BaseNewsSource):
    """财联社电报 — direct HTTP to cls.cn."""

    name = "cls"
    label = "财联社"
    category = "market"

    def fetch_market(self, limit: int = 30) -> list[dict]:
        """Fetch real-time telegraph from CLS."""
        raw = self._fetch(page_size=min(limit, 50))
        normalized = self._normalize(raw)
        return normalized[:limit]

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        """Filter telegraph by symbol keyword (best-effort)."""
        raw = self._fetch(page_size=50)
        normalized = self._normalize(raw)
        # Filter: title or summary contains the symbol
        filtered: list[dict] = []
        for a in normalized:
            text = f"{a.get('title', '')} {a.get('summary', '')}"
            if symbol.replace(".SZ", "").replace(".SH", "") in text or symbol in text:
                filtered.append(a)
        return filtered[:limit]

    def _fetch(self, page_size: int = 50) -> list[dict]:
        """Raw fetch from CLS telegraph API."""
        try:
            url = "https://www.cls.cn/nodeapi/telegraphList"
            params = {"rn": str(page_size), "page": "1"}
            headers = {
                "User-Agent": UA,
                "Referer": "https://www.cls.cn/",
            }
            r = requests.get(url, params=params, headers=headers, timeout=10)
            d = r.json()

            items = d.get("data", {}).get("roll_data", [])
            return [
                {
                    "title": item.get("title", "") or item.get("brief", ""),
                    "url": "",
                    "content": (item.get("content", "") or item.get("brief", ""))[:200],
                    "time": str(item.get("ctime", "")),
                }
                for item in items
            ]
        except Exception as e:
            logger.debug("CLS telegraph fetch failed: %s", e)
            return []

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles
