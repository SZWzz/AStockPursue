"""Financial news aggregation module.

Aggregates financial news from multiple free sources:
  - DuckDuckGo web search (free, no API key)
  - RSS feeds from major financial sites (planned)
  - Economic calendar data

Usage:
    from backtest.loaders.news import NewsFetcher
    fetcher = NewsFetcher()
    news = fetcher.search_news("A股 新能源", max_results=10)
    calendar = fetcher.get_economic_calendar()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetch financial news from free sources."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Web search based news
    # ------------------------------------------------------------------

    def search_news(
        self,
        query: str,
        max_results: int = 10,
        language: str = "zh",
        region: str = "cn",
    ) -> List[Dict[str, str]]:
        """Search financial news via DuckDuckGo.

        Args:
            query: Search query. Prefix "财经 " is automatically added for Chinese searches.
            max_results: Max results to return (default 10, max 20).
            language: Search language ('zh', 'en').
            region: Search region ('cn', 'us', 'hk').
        """
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            full_query = f"财经 {query}" if language == "zh" else f"finance {query}"
            with DDGS() as ddgs:
                raw = list(ddgs.text(
                    full_query,
                    max_results=min(max_results, 20),
                    region=region,
                ))

            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "web_search",
                }
                for r in raw
            ]
        except ImportError:
            logger.warning("DuckDuckGo search not available. Install: pip install ddgs")
            return []
        except Exception as e:
            logger.warning("News search failed for '%s': %s", query, e)
            return []

    # ------------------------------------------------------------------
    # Topic-specific news queries
    # ------------------------------------------------------------------

    def fetch_market_news(self, max_results: int = 10) -> List[Dict[str, str]]:
        """Fetch general market news."""
        queries = [
            "A股 市场 行情 今日",
            "stock market news today",
        ]
        results: List[Dict[str, str]] = []
        for q in queries:
            results.extend(self.search_news(q, max_results=max_results // len(queries) + 1))
        return _deduplicate(results)[:max_results]

    def fetch_sector_news(self, sector: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Fetch news for a specific sector.

        Args:
            sector: Sector name (e.g. '新能源', '半导体', 'AI').
        """
        query = f"{sector} 板块 行情"
        return self.search_news(query, max_results=max_results)

    def fetch_stock_news(self, symbol: str, name: str = "", max_results: int = 5) -> List[Dict[str, str]]:
        """Fetch news for a specific stock.

        Args:
            symbol: Stock code (e.g. '000001.SZ', 'AAPL.US').
            name: Stock name for better search results.
        """
        query = f"{symbol} {name} 股票 新闻".strip()
        return self.search_news(query, max_results=max_results)

    # ------------------------------------------------------------------
    # Economic calendar
    # ------------------------------------------------------------------

    def get_economic_calendar(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming economic events for the next N days.

        Currently provides a template of known recurring events. In the future
        this can be extended to scrape real calendar data from investing.com or
        use a paid API (Tradier, Financial Modeling Prep, etc.).
        """
        today = datetime.now()
        events: List[Dict[str, Any]] = []

        # Generate the next N weekdays
        current = today
        days_added = 0
        while days_added < days:
            if current.weekday() < 5:  # Monday-Friday
                daily_events = _get_daily_template(current)
                events.extend(daily_events)
                days_added += 1
            current += timedelta(days=1)

        return events[:days * 3]


def _get_daily_template(date: datetime) -> List[Dict[str, Any]]:
    """Return template economic events for a given date."""
    weekday = date.weekday()
    events: List[Dict[str, Any]] = []

    # US weekly jobless claims — Thursday
    if weekday == 3:
        events.append({
            "date": date.strftime("%Y-%m-%d"),
            "time": "20:30",
            "country": "US",
            "event": "初请失业金人数",
            "event_en": "Initial Jobless Claims",
            "importance": "high",
        })

    # EIA crude oil inventories — Wednesday
    if weekday == 2:
        events.append({
            "date": date.strftime("%Y-%m-%d"),
            "time": "22:30",
            "country": "US",
            "event": "EIA原油库存",
            "event_en": "EIA Crude Oil Inventories",
            "importance": "medium",
        })

    # China PMI — end of month
    if date.day >= 28:
        events.append({
            "date": date.strftime("%Y-%m-%d"),
            "time": "09:30",
            "country": "CN",
            "event": "中国官方PMI (预计)",
            "event_en": "China Official PMI (expected)",
            "importance": "high",
        })

    # US non-farm payrolls — first Friday
    if weekday == 4 and date.day <= 7:
        events.append({
            "date": date.strftime("%Y-%m-%d"),
            "time": "20:30",
            "country": "US",
            "event": "非农就业数据 (预计)",
            "event_en": "Non-Farm Payrolls (expected)",
            "importance": "high",
        })

    # FOMC meeting — roughly every 6 weeks (placeholder)
    if weekday == 2 and 15 <= date.day <= 22:
        events.append({
            "date": date.strftime("%Y-%m-%d"),
            "time": "02:00",
            "country": "US",
            "event": "FOMC会议纪要 (预计窗口)",
            "event_en": "FOMC Minutes (expected window)",
            "importance": "high",
        })

    return events


def _deduplicate(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Remove duplicate news by URL."""
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)
    return unique
