"""East Money stock news — direct HTTP API (from 01.md).

Source: search-api-web.eastmoney.com (JSONP)
Returns: individual stock news articles with title, content, time, source, url
"""

from __future__ import annotations

import json
import logging
import re

import requests

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class EastMoneyStockSource(BaseNewsSource):
    """东财个股新闻 — direct HTTP to search-api-web.eastmoney.com."""

    name = "eastmoney_stock"
    label = "东财个股"
    category = "stock"

    def fetch_stock(self, symbol: str, limit: int = 10) -> list[dict]:
        """Fetch stock-specific news from East Money."""
        raw = self._fetch(symbol, limit)
        return self._normalize(raw)[:limit]

    def fetch_market(self, limit: int = 10) -> list[dict]:
        """No market-wide endpoint for this source."""
        return []

    def _fetch(self, code: str, page_size: int = 20) -> list[dict]:
        """Raw fetch from East Money search API (JSONP)."""
        try:
            cb = "jQuery_news"
            url = "https://search-api-web.eastmoney.com/search/jsonp"
            inner_params = json.dumps({
                "uid": "",
                "keyword": code,
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "clientVersion": "curr",
                "param": {
                    "cmsArticleWebOld": {
                        "searchScope": "default",
                        "sort": "default",
                        "pageIndex": 1,
                        "pageSize": min(page_size, 50),
                        "preTag": "",
                        "postTag": "",
                    },
                },
            }, separators=(',', ':'))

            params = {"cb": cb, "param": inner_params}
            headers = {
                "User-Agent": UA,
                "Referer": "https://so.eastmoney.com/",
            }
            r = requests.get(url, params=params, headers=headers, timeout=15)

            # Parse JSONP
            text = r.text
            idx_open = text.index("(")
            idx_close = text.rindex(")")
            json_str = text[idx_open + 1:idx_close]
            d = json.loads(json_str)

            articles_raw = d.get("result", {}).get("cmsArticleWebOld", [])
            # cmsArticleWebOld is either a list or a dict with "list" key
            if isinstance(articles_raw, dict):
                articles_raw = articles_raw.get("list", [])
            elif not isinstance(articles_raw, list):
                articles_raw = []
            return [
                {
                    "title": re.sub(r'<[^>]+>', '', a.get("title", "")),
                    "url": a.get("url", ""),
                    "content": re.sub(r'<[^>]+>', '', a.get("content", ""))[:200],
                    "time": a.get("date", ""),
                    "source_name": a.get("mediaName", ""),
                }
                for a in articles_raw
            ]

        except Exception as e:
            logger.debug("EastMoney stock news fetch failed for %s: %s", code, e)
            return []

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                # Use media name in summary prefix if available
                media = r.get("source_name", "")
                if media and a.get("summary"):
                    a["summary"] = f"[{media}] {a['summary']}"[:200]
                articles.append(a)
        return articles
