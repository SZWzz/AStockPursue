"""East Money global 7x24 news — direct HTTP API (from 01.md).

Source: np-weblist.eastmoney.com
Returns: rolling 7x24 financial news headlines with title, summary, time
"""

from __future__ import annotations

import logging
import uuid

import requests

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class EastMoneyGlobalSource(BaseNewsSource):
    """东财全球 7x24 资讯 — direct HTTP to np-weblist.eastmoney.com."""

    name = "eastmoney_global"
    label = "东财全球"
    category = "market"

    def fetch_market(self, limit: int = 30) -> list[dict]:
        """Fetch 7x24 global financial news."""
        raw = self._fetch(page_size=min(limit, 50))
        normalized = self._normalize(raw)
        return normalized[:limit]

    def fetch_stock(self, symbol: str, limit: int = 5) -> list[dict]:
        """Filter global news by symbol keyword (best-effort)."""
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
        """Raw fetch from East Money global news API."""
        try:
            url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
            params = {
                "client": "web",
                "biz": "web_724",
                "fastColumn": "102",
                "sortEnd": "",
                "pageSize": str(page_size),
                "req_trace": str(uuid.uuid4()),
            }
            headers = {
                "User-Agent": UA,
                "Referer": "https://kuaixun.eastmoney.com/",
            }
            r = requests.get(url, params=params, headers=headers, timeout=10)
            d = r.json()

            items = d.get("data", {}).get("fastNewsList", [])
            return [
                {
                    "title": item.get("title", ""),
                    "url": "",
                    "summary": (item.get("summary", "") or "")[:200],
                    "time": item.get("showTime", ""),
                }
                for item in items
            ]
        except Exception as e:
            logger.debug("EastMoney global news fetch failed: %s", e)
            return []

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                articles.append(a)
        return articles
