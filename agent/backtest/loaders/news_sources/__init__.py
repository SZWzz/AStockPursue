"""Multi-source news aggregation.

Sources (10 total, 4 implementation types):

Direct HTTP (from 01.md, zero new deps):
  - EastMoneyStockSource     — 东财个股新闻 (search-api-web.eastmoney.com)
  - EastMoneyGlobalSource    — 东财全球 7x24 资讯 (np-weblist.eastmoney.com)
  - CLSTelegraphSource       — 财联社电报 (www.cls.cn)
  - CNINFOSource             — 巨潮公告 (www.cninfo.com.cn)

akshare (existing dep):
  - SinaFinanceSource        — 新浪财经全球快讯
  - XueqiuSource             — 雪球热股排行
  - FutuSource               — 富途牛牛快讯
  - THSSource                — 同花顺快讯

Third-party libraries:
  - GNewsSource              — Google News RSS (gnews, free)
  - NewsAPISource            — NewsAPI (newsapi-python, optional API key)

Usage:
    from backtest.loaders.news_sources import AggregateNewsFetcher
    fetcher = AggregateNewsFetcher()
    articles = fetcher.fetch_stock_news("000001", limit=20)
    articles = fetcher.fetch_market_news(limit=30)
"""

from __future__ import annotations

from .base import BaseNewsSource, normalize_article
from .duckduckgo import DuckDuckGoSource
from .eastmoney_stock import EastMoneyStockSource
from .eastmoney_global import EastMoneyGlobalSource
from .cls_telegraph import CLSTelegraphSource
from .cninfo import CNINFOSource
from .akshare_sources import SinaFinanceSource, XueqiuSource, FutuSource, THSSource
from .gnews import GNewsSource
from .newsapi import NewsAPISource
from .aggregate import AggregateNewsFetcher

__all__ = [
    "BaseNewsSource",
    "normalize_article",
    "DuckDuckGoSource",
    "EastMoneyStockSource",
    "EastMoneyGlobalSource",
    "CLSTelegraphSource",
    "CNINFOSource",
    "SinaFinanceSource",
    "XueqiuSource",
    "FutuSource",
    "THSSource",
    "GNewsSource",
    "NewsAPISource",
    "AggregateNewsFetcher",
]
