"""AggregateNewsFetcher — fan-out to all sources, merge, deduplicate, sort.

Usage:
    from backtest.loaders.news_sources import AggregateNewsFetcher
    fetcher = AggregateNewsFetcher()
    articles = fetcher.fetch_stock_news("000001", limit=20)
    articles = fetcher.fetch_market_news(limit=30)
    freshness = fetcher.get_source_freshness()
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .base import (
    SOURCE_META,
    BaseNewsSource,
    deduplicate_by_title_similarity,
    deduplicate_by_url,
)
from .duckduckgo import DuckDuckGoSource
from .eastmoney_stock import EastMoneyStockSource
from .eastmoney_global import EastMoneyGlobalSource
from .cls_telegraph import CLSTelegraphSource
from .cninfo import CNINFOSource
from .akshare_sources import SinaFinanceSource, XueqiuSource, FutuSource, THSSource
from .gnews import GNewsSource
from .newsapi import NewsAPISource

logger = logging.getLogger(__name__)

# Default source instances (lazy init, shared across calls)
_SOURCES: list[BaseNewsSource] | None = None


def _get_all_sources() -> list[BaseNewsSource]:
    """Lazy-init all available sources."""
    global _SOURCES
    if _SOURCES is not None:
        return _SOURCES

    _SOURCES = [
        EastMoneyStockSource(),
        EastMoneyGlobalSource(),
        CLSTelegraphSource(),
        CNINFOSource(),
        SinaFinanceSource(),
        XueqiuSource(),
        FutuSource(),
        THSSource(),
        GNewsSource(),
        NewsAPISource(),
        DuckDuckGoSource(),
    ]
    return _SOURCES


class AggregateNewsFetcher:
    """Orchestrate multiple news sources with parallel fan-out.

    Public API matches the existing NewsFetcher for backward compatibility:
      - search_news(query, ...)
      - fetch_market_news(max_results)
      - fetch_stock_news(symbol, name, max_results)
      - fetch_sector_news(sector, max_results)
      - get_economic_calendar(days)

    Plus new methods:
      - get_source_freshness()
      - get_available_sources()
    """

    def __init__(self, max_workers: int = 8) -> None:
        self._max_workers = max_workers
        self._sources = _get_all_sources()

    # ── Public API (backward compat) ───────────────────────────────────

    def search_news(
        self,
        query: str,
        max_results: int = 10,
        language: str = "zh",
        region: str = "cn",
    ) -> list[dict]:
        """Search across all sources (fan-out)."""
        raw = self._fanout_market(limit=max_results)
        # Also keep duckduckgo traditional search for keyword precision
        ddg = DuckDuckGoSource()
        raw += ddg._search(query, max_results=min(max_results, 10), language=language, region=region)  # type: ignore[operator]
        return self._merge(raw)[:max_results]

    def fetch_market_news(self, max_results: int = 10) -> list[dict]:
        """Fetch general market news from all sources."""
        raw = self._fanout_market(limit=max_results)
        return self._merge(raw)[:max_results]

    def fetch_stock_news(self, symbol: str, name: str = "", max_results: int = 5) -> list[dict]:
        """Fetch stock-specific news from all sources."""
        raw = self._fanout_stock(symbol.strip(), limit=max_results)
        return self._merge(raw)[:max_results]

    def fetch_sector_news(self, sector: str, max_results: int = 5) -> list[dict]:
        """Fetch sector news — uses DuckDuckGo + market news filtered."""
        ddg = DuckDuckGoSource()
        query_results = ddg._search(f"{sector} 板块 行情", max_results=min(max_results, 10))  # type: ignore[operator]
        normalized = ddg._normalize(query_results)
        market = self._fanout_market(limit=max_results)
        # Filter market news for sector keyword
        for a in self._merge(market):
            text = f"{a.get('title', '')} {a.get('summary', '')}"
            if sector in text:
                normalized.append(a)
        return self._merge(normalized)[:max_results]

    def get_economic_calendar(self, days: int = 7) -> list[dict]:
        """Return economic calendar (delegated to original impl)."""
        from backtest.loaders.news import NewsFetcher as _OldFetcher
        try:
            return _OldFetcher().get_economic_calendar(days)
        except Exception:
            return []

    # ── New Public API ────────────────────────────────────────────────

    def get_source_freshness(self) -> dict[str, dict]:
        """Return availability + last-update info for each source."""
        from src.db.sentiment_store import get_source_freshness as _db_freshness
        return _db_freshness()

    def get_available_sources(self) -> list[dict]:
        """Return metadata for all registered sources, including availability."""
        result: list[dict] = []
        for s in self._sources:
            meta = SOURCE_META.get(s.name, {"id": s.name, "label": s.name, "category": "market"})
            result.append({
                "id": s.name,
                "label": s.label,
                "category": s.category,
                "available": s.is_available(),
            })
        return result

    # ── Internal ──────────────────────────────────────────────────────

    def _fanout_market(self, limit: int) -> list[dict]:
        """Fan-out to all sources' fetch_market() in parallel."""
        return self._fanout("market", limit=limit)

    def _fanout_stock(self, symbol: str, limit: int) -> list[dict]:
        """Fan-out to all sources' fetch_stock() in parallel."""
        return self._fanout("stock", symbol=symbol, limit=limit)

    def _fanout(self, mode: str, symbol: str = "", limit: int = 10) -> list[dict]:
        """Parallel fan-out: call fetch_market or fetch_stock on every source."""
        available = [s for s in self._sources if s.is_available()]
        if not available:
            logger.warning("No news sources available")
            return []

        results: list[dict] = []

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(available))) as executor:
            futures: dict = {}

            for src in available:
                if mode == "stock":
                    futures[executor.submit(src.fetch_stock, symbol, limit)] = src.name
                else:
                    futures[executor.submit(src.fetch_market, limit)] = src.name

            for future in as_completed(futures):
                src_name = futures[future]
                try:
                    articles = future.result(timeout=30)
                    if articles:
                        logger.debug("Source '%s' returned %d articles", src_name, len(articles))
                    results.extend(articles)
                except Exception as e:
                    logger.debug("Source '%s' failed in fan-out: %s", src_name, e)

        return results

    def _merge(self, articles: list[dict]) -> list[dict]:
        """Deduplicate and sort a list of normalized articles."""
        # Step 1: URL dedup
        unique = deduplicate_by_url(articles)
        # Step 2: Title similarity dedup
        unique = deduplicate_by_title_similarity(unique, threshold=0.85)
        # Step 3: Sort by published_at descending (nulls last)
        unique.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        return unique
