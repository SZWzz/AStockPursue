"""Financial news aggregation module.

Now powered by AggregateNewsFetcher — fans out to 10 sources in parallel:
  - East Money (stock news + global 7x24)
  - CLS Telegraph (real-time)
  - CNINFO (A-share announcements)
  - Sina Finance, Xueqiu, Futu, THS (via akshare)
  - GNews (Google News RSS)
  - NewsAPI (optional API key)
  - DuckDuckGo web search (fallback)

Backward-compatible: NewsFetcher is an alias for AggregateNewsFetcher.
All existing call sites continue to work unchanged.

Usage:
    from backtest.loaders.news import NewsFetcher
    fetcher = NewsFetcher()
    news = fetcher.search_news("A股 新能源", max_results=10)
    news = fetcher.fetch_stock_news("000001", max_results=20)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backtest.loaders.news_sources.aggregate import AggregateNewsFetcher

logger = logging.getLogger(__name__)


class NewsFetcher(AggregateNewsFetcher):
    """Backward-compatible alias for AggregateNewsFetcher.

    Delegates all news fetching to the multi-source aggregate engine.
    The economic calendar is still the template-based fallback.
    """

    # search_news, fetch_market_news, fetch_stock_news, fetch_sector_news
    # are all inherited from AggregateNewsFetcher.

    def get_economic_calendar(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming economic events (template-based fallback)."""
        today = datetime.now()
        events: List[Dict[str, Any]] = []
        current = today
        days_added = 0
        while days_added < days:
            if current.weekday() < 5:
                daily_events = _get_daily_template(current)
                events.extend(daily_events)
                days_added += 1
            current += timedelta(days=1)
        return events[:days * 3]


def _get_daily_template(date: datetime) -> List[Dict[str, Any]]:
    """Return template economic events for a given date."""
    weekday = date.weekday()
    events: List[Dict[str, Any]] = []
    if weekday == 3:
        events.append({
            "date": date.strftime("%Y-%m-%d"), "time": "20:30", "country": "US",
            "event": "初请失业金人数", "event_en": "Initial Jobless Claims", "importance": "high",
        })
    if weekday == 2:
        events.append({
            "date": date.strftime("%Y-%m-%d"), "time": "22:30", "country": "US",
            "event": "EIA原油库存", "event_en": "EIA Crude Oil Inventories", "importance": "medium",
        })
    if date.day >= 28:
        events.append({
            "date": date.strftime("%Y-%m-%d"), "time": "09:30", "country": "CN",
            "event": "中国官方PMI (预计)", "event_en": "China Official PMI (expected)", "importance": "high",
        })
    if weekday == 4 and date.day <= 7:
        events.append({
            "date": date.strftime("%Y-%m-%d"), "time": "20:30", "country": "US",
            "event": "非农就业数据 (预计)", "event_en": "Non-Farm Payrolls (expected)", "importance": "high",
        })
    if weekday == 2 and 15 <= date.day <= 22:
        events.append({
            "date": date.strftime("%Y-%m-%d"), "time": "02:00", "country": "US",
            "event": "FOMC会议纪要 (预计窗口)", "event_en": "FOMC Minutes (expected window)", "importance": "high",
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
