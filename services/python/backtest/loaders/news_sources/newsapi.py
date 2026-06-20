"""NewsAPI source — optional, requires API key.

Free tier: 100 requests/day.
Get API key: https://newsapi.org/register

Set via environment variable: NEWSAPI_KEY
Or pass directly to NewsAPISource(api_key="...").

Install: pip install newsapi-python
"""

from __future__ import annotations

import logging
import os

from .base import BaseNewsSource, normalize_article

logger = logging.getLogger(__name__)


class NewsAPISource(BaseNewsSource):
    """NewsAPI — international news aggregation (optional API key)."""

    name = "newsapi"
    label = "NewsAPI"
    category = "international"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("NEWSAPI_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            return None
        try:
            from newsapi import NewsApiClient
            self._client = NewsApiClient(api_key=self._api_key)
            return self._client
        except ImportError:
            logger.debug("NewsAPI not available (newsapi-python not installed)")
            return None
        except Exception as e:
            logger.debug("NewsAPI client init failed: %s", e)
            return None

    def fetch_market(self, limit: int = 20) -> list[dict]:
        raw: list[dict] = []
        client = self._get_client()
        if client is None:
            return []

        try:
            # Top business headlines
            resp = client.get_top_headlines(category="business", language="en", page_size=min(limit, 20))
            raw.extend(self._parse_response(resp))
        except Exception as e:
            logger.debug("NewsAPI top headlines failed: %s", e)

        try:
            # China/Asia financial news
            resp = client.get_everything(
                q="China OR Asia stock market finance",
                language="en",
                sort_by="publishedAt",
                page_size=min(limit, 20),
            )
            raw.extend(self._parse_response(resp))
        except Exception as e:
            logger.debug("NewsAPI everything search failed: %s", e)

        return self._normalize(raw)[:limit]

    def fetch_stock(self, symbol: str, limit: int = 10) -> list[dict]:
        client = self._get_client()
        if client is None:
            return []

        try:
            resp = client.get_everything(
                q=f"{symbol} stock",
                language="en",
                sort_by="publishedAt",
                page_size=min(limit, 20),
            )
            return self._normalize(self._parse_response(resp))[:limit]
        except Exception as e:
            logger.debug("NewsAPI stock search failed for %s: %s", symbol, e)
            return []

    def is_available(self) -> bool:
        return bool(self._api_key) and self._get_client() is not None

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _parse_response(resp: dict) -> list[dict]:
        """Parse NewsAPI response into raw article dicts."""
        if resp.get("status") != "ok":
            return []
        articles = resp.get("articles", [])
        return [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "description": a.get("description", ""),
                "publishedAt": a.get("publishedAt", ""),
                "source_name": (a.get("source", {}) or {}).get("name", ""),
            }
            for a in articles
        ]

    def _normalize(self, raw_list: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for r in raw_list:
            a = normalize_article(r, self.name)
            if a:
                source_name = r.get("source_name", "")
                if source_name and a.get("summary"):
                    a["summary"] = f"[{source_name}] {a['summary']}"[:200]
                articles.append(a)
        return articles
