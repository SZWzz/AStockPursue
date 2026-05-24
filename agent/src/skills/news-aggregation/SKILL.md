---
name: news-aggregation
description: Financial news aggregation — search via DuckDuckGo, sector-specific queries, stock-specific news, economic calendar. Free, no API key.
category: data-source
---
# News Aggregation

## Overview

Aggregates financial news from free web search (DuckDuckGo) and provides an economic calendar template. **No API key required for basic usage.**

The module is at `backtest/loaders/news.py` and is also exposed as an Agent tool (`financial_news`).

## Features

### 1. General Market News
```python
from backtest.loaders.news import NewsFetcher

fetcher = NewsFetcher()
news = fetcher.fetch_market_news(max_results=10)
```

### 2. Sector News
```python
tech_news = fetcher.fetch_sector_news("半导体", max_results=5)
energy_news = fetcher.fetch_sector_news("新能源", max_results=5)
```

### 3. Stock-Specific News
```python
apple_news = fetcher.fetch_stock_news("AAPL.US", name="Apple", max_results=5)
moutai_news = fetcher.fetch_stock_news("600519.SH", name="茅台", max_results=5)
```

### 4. Custom Search
```python
results = fetcher.search_news(
    query="美联储 利率 决议",
    max_results=10,
    language="zh",
    region="cn",
)
```

### 5. Economic Calendar
```python
calendar = fetcher.get_economic_calendar(days=7)
# Returns upcoming events with: date, time, country, event, importance
```

## Agent Tool

The `financial_news` tool is available to the AI agent:
- "最近A股有什么新闻？" → `financial_news` with topic="market"
- "帮我找一下茅台的最新消息" → `financial_news` with topic="stock", symbol="600519.SH"
- "这周有什么重要经济数据？" → `financial_news` with topic="calendar"

## Economic Calendar Coverage

| Event | Frequency | Country |
|-------|-----------|---------|
| Initial Jobless Claims | Weekly (Thu) | US |
| EIA Crude Oil Inventories | Weekly (Wed) | US |
| Non-Farm Payrolls | Monthly (1st Fri) | US |
| FOMC Minutes | ~6 weeks | US |
| China Official PMI | Monthly (end) | CN |

> **Note**: The calendar is template-based. For real-time calendar data, consider integrating a paid API (Tradier, Financial Modeling Prep, etc.).

## Limitations

- DuckDuckGo search may return limited results for niche topics
- News results are snippets, not full articles — use `read_url` tool to fetch full content
- Economic calendar is template-based, not real-time
