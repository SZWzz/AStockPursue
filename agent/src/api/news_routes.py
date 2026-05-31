"""News Sentiment REST API — multi-source news with SnowNLP scoring, SSE streaming.

Three-layer caching:
  L1: In-memory TTL cache (5 min default, per-source TTL varies)
  L2: PostgreSQL vt_news_items (DB-first read, avoids external API calls)
  L3: External APIs — 10 sources via AggregateNewsFetcher (parallel fan-out)

Data sources: East Money (stock + global 7x24), CLS Telegraph, CNINFO,
  Sina, Xueqiu, Futu, THS, GNews, NewsAPI, DuckDuckGo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from datetime import date, datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth
from src.services.sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

# ── Module-level TTL caches ──────────────────────────────────────────────────

_CACHE_TTL: float = 300.0  # 5 minutes

_feed_cache: dict[str, list[dict]] = {}
_feed_cache_ts: dict[str, float] = {}

_sentiment_cache: dict[str, dict] = {}
_sentiment_cache_ts: dict[str, float] = {}

_trending_cache: list[dict] | None = None
_trending_cache_ts: float = 0.0

_market_cache: dict | None = None
_market_cache_ts: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_and_score(
    symbol: str = "",
    limit: int = 20,
    force_refresh: bool = False,
) -> list[dict]:
    """DB-first fetch: check cache → external API if stale.

    Flow:
      1. If force_refresh=False, try DB cache first
      2. If cache hit rate >= 70%, return cached
      3. Otherwise, fan out to all sources via AggregateNewsFetcher
      4. Score with SentimentAnalyzer, persist to DB, return
    """
    from backtest.loaders.news import NewsFetcher
    from src.db.sentiment_store import get_recent_news, save_news_items

    upper = symbol.strip().upper() if symbol else ""
    analyzer = SentimentAnalyzer()

    # Step 1: Try DB cache first (unless force refresh)
    if not force_refresh:
        cached = get_recent_news(symbol=upper, limit=limit * 2, max_age_minutes=5)
        if len(cached) >= limit * 0.7:
            # Cache is warm enough — return directly
            return cached[:limit]

    # Step 2: Cache miss or stale — fetch from external sources
    fetcher = NewsFetcher()
    if upper:
        raw = fetcher.fetch_stock_news(upper, name="", max_results=limit)
    else:
        raw = fetcher.fetch_market_news(max_results=limit)

    # Step 3: Score and build articles
    articles: list[dict] = []
    for r in raw:
        text = f"{r.get('title', '')} {r.get('summary', '')}"
        score = analyzer.analyze_text(text)
        articles.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "source": r.get("source", "web_search"),
            "source_label": r.get("source_label", r.get("source", "")),
            "summary": (r.get("summary", "") or r.get("snippet", ""))[:200],
            "published_at": r.get("published_at", ""),
            "sentiment_score": score,
            "sentiment_label": "positive" if score > 0.6 else ("negative" if score < 0.4 else "neutral"),
        })

    # Step 4: Persist to DB (fire-and-forget)
    if articles:
        try:
            save_news_items(articles)
        except Exception:
            logger.warning("Failed to persist fetched articles to DB", exc_info=True)

    # Step 5: Merge with any remaining cached items we didn't fetch from
    if not force_refresh:
        cached = get_recent_news(symbol=upper, limit=limit * 2, max_age_minutes=30)
        seen_titles = {a.get("title", "") for a in articles}
        for c in cached:
            if c.get("title", "") not in seen_titles:
                articles.append(c)

    return articles[:limit]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/feed")
async def get_news_feed(
    symbol: str = "",
    limit: int = Query(20, ge=1, le=100),
    refresh: bool = Query(False),
    auth: dict = Depends(require_auth),
):
    """Get latest news with sentiment scores (cached 5 min)."""
    cache_key = f"feed:{symbol or 'market'}:{limit}"
    now = time.monotonic()
    cached = _feed_cache.get(cache_key)
    cached_ts = _feed_cache_ts.get(cache_key, 0.0)

    if not refresh and cached is not None and (now - cached_ts) < _CACHE_TTL:
        return {"articles": cached, "total": len(cached), "symbol": symbol or "market", "cached": True}

    articles = _fetch_and_score(symbol=symbol, limit=limit)

    # Persist to DB (fire-and-forget — log but don't fail the response)
    from src.db.sentiment_store import save_news_items
    try:
        save_news_items(articles)
    except Exception:
        logger.warning("Failed to persist news feed articles to DB", exc_info=True)

    _feed_cache[cache_key] = articles
    _feed_cache_ts[cache_key] = now
    return {"articles": articles, "total": len(articles), "symbol": symbol or "market", "cached": False}


@router.get("/sentiment/{symbol}")
async def get_stock_sentiment(
    symbol: str,
    refresh: bool = Query(False),
    auth: dict = Depends(require_auth),
):
    """Get sentiment history and aggregate for a stock (cached 5 min)."""
    upper = symbol.strip().upper()
    now = time.monotonic()
    cached = _sentiment_cache.get(upper)
    cached_ts = _sentiment_cache_ts.get(upper, 0.0)

    if not refresh and cached is not None and (now - cached_ts) < _CACHE_TTL:
        return {**cached, "cached": True}

    articles = _fetch_and_score(symbol=symbol, limit=20)

    scores = [a.get("sentiment_score", 0.5) for a in articles]
    result = {
        "symbol": upper,
        "sentiment_mean": round(float(np.mean(scores)), 4) if scores else 0.5,
        "sentiment_std": round(float(np.std(scores, ddof=1)), 4) if len(scores) > 1 else 0.0,
        "news_count": len(articles),
        "trending_score": round(float(np.mean(scores)) * min(1.0, len(scores) / 10), 4) if scores else 0.0,
        "recent_articles": articles[:10],
    }

    # Persist to DB
    from src.db.sentiment_store import save_news_items, save_stock_sentiment
    from datetime import date
    try:
        save_news_items(articles)
        save_stock_sentiment(
            symbol=upper,
            date=str(date.today()),
            sentiment_mean=result["sentiment_mean"],
            sentiment_std=result["sentiment_std"],
            news_count=result["news_count"],
            trending_score=result["trending_score"],
        )
    except Exception:
        logger.warning("Failed to persist stock sentiment for %s to DB", upper, exc_info=True)

    _sentiment_cache[upper] = result
    _sentiment_cache_ts[upper] = now
    result["cached"] = False
    return result


@router.get("/trending")
async def get_trending_topics(
    limit: int = 10,
    refresh: bool = Query(False),
    auth: dict = Depends(require_auth),
):
    """Get trending topics with sentiment aggregation from real news (cached 5 min)."""
    global _trending_cache, _trending_cache_ts
    now = time.monotonic()

    if not refresh and _trending_cache is not None and (now - _trending_cache_ts) < _CACHE_TTL:
        return {"topics": _trending_cache, "cached": True}

    articles = _fetch_and_score(limit=50)

    # Extract topics via keyword matching (no NLP topic model yet)
    topic_keywords: dict[str, list[str]] = {
        "降准降息": ["降准", "降息", "LPR", "利率", "MLF", "逆回购"],
        "新能源汽车": ["新能源", "电动车", "电池", "充电", "比亚迪", "宁德", "锂电"],
        "白酒消费": ["白酒", "茅台", "消费", "五粮液", "食品"],
        "半导体芯片": ["半导体", "芯片", "集成电路", "光刻", "AI芯片"],
        "医药创新": ["医药", "创新药", "FDA", "临床", "生物药", "疫苗"],
        "房地产": ["房地产", "房企", "债务", "商品房", "楼市", "房贷"],
        "AI人工智能": ["人工智能", "AI", "大模型", "GPT", "DeepSeek", "智能"],
        "货币政策": ["央行", "货币政策", "降准", "降息", "流动性", "逆回购"],
        "外贸出口": ["出口", "贸易", "关税", "外贸", "跨境电商"],
        "电力能源": ["电力", "能源", "光伏", "风电", "储能", "煤炭"],
    }

    topic_counter: Counter[str] = Counter()
    topic_sents: dict[str, list[float]] = {}

    for a in articles:
        title = a.get("title", "")
        summary = a.get("summary", "")
        text = f"{title} {summary}"
        score = a.get("sentiment_score", 0.5)

        for topic, kws in topic_keywords.items():
            if any(kw in text for kw in kws):
                topic_counter[topic] += 1
                topic_sents.setdefault(topic, []).append(score)

    topics = []
    for topic, count in topic_counter.most_common(limit * 2):
        scores = topic_sents.get(topic, [0.5])
        topics.append({
            "topic": topic,
            "count": count,
            "sentiment_mean": round(float(np.mean(scores)), 4),
            "trending_score": round(count * float(np.mean(scores)), 2),
        })
    topics.sort(key=lambda x: x["trending_score"], reverse=True)
    topics = topics[:limit]

    # Persist underlying articles to DB
    from src.db.sentiment_store import save_news_items
    try:
        save_news_items(articles)
    except Exception:
        logger.warning("Failed to persist trending articles to DB", exc_info=True)

    _trending_cache = topics
    _trending_cache_ts = now
    return {"topics": topics, "cached": False}


@router.get("/market-sentiment")
async def get_market_sentiment(
    refresh: bool = Query(False),
    auth: dict = Depends(require_auth),
):
    """Get market-wide sentiment overview (VIX, DXY, yield, F&G, news sentiment) — cached 5 min."""
    global _market_cache, _market_cache_ts
    now = time.monotonic()

    if not refresh and _market_cache is not None and (now - _market_cache_ts) < _CACHE_TTL:
        return {**_market_cache, "cached": True}
    import numpy as np

    result: dict = {
        "overall_sentiment": 0.5,
        "vix": {"current": 0, "level": "unknown", "trend": "unknown"},
        "dxy": {"current": 0, "level": "unknown", "trend": "unknown"},
        "yield_spread": {"spread": 0.0, "level": "unknown", "signal": "neutral"},
        "fear_greed": {"value": 50, "classification": "neutral"},
        "news_sentiment_mean": 0.5,
        "news_sentiment_count": 0,
    }

    # 1) Market sentiment indicators via SentimentFetcher
    try:
        from backtest.loaders.sentiment import SentimentFetcher
        sf = SentimentFetcher()
        data = sf.fetch_all()

        # VIX
        vix_data = data.get("vix", {})
        result["vix"] = {
            "current": vix_data.get("value", 0),
            "level": vix_data.get("level", "unknown"),
            "trend": vix_data.get("trend", "unknown"),
        }

        # DXY
        dxy_data = data.get("dxy", {})
        result["dxy"] = {
            "current": dxy_data.get("value", 0),
            "level": dxy_data.get("level", "unknown"),
            "trend": dxy_data.get("trend", "unknown"),
        }

        # Yield curve
        yc = data.get("yield_curve", {})
        result["yield_spread"] = {
            "spread": yc.get("spread", 0.0),
            "level": yc.get("level", "unknown"),
            "signal": yc.get("signal", "neutral"),
        }

        # Fear & Greed
        fg = data.get("fear_greed", {})
        result["fear_greed"] = {
            "value": fg.get("value", 50),
            "classification": fg.get("classification", "neutral"),
        }
    except Exception as e:
        logger.warning("Market sentiment indicators fetch failed: %s", e)

    # 2) News sentiment — aggregate recent market news
    market_articles: list[dict] = []
    try:
        market_articles = _fetch_and_score(limit=30)
        scores = [a.get("sentiment_score", 0.5) for a in market_articles]
        if scores:
            result["news_sentiment_mean"] = round(float(np.mean(scores)), 4)
            result["news_sentiment_count"] = len(scores)
            # Overall = weighted blend of news sentiment (70%) + neutral (30%)
            result["overall_sentiment"] = round(float(np.mean(scores)) * 0.7 + 0.5 * 0.3, 4)
    except Exception as e:
        logger.warning("News sentiment fetch for market overview failed: %s", e)

    # Persist news articles to DB
    from src.db.sentiment_store import save_news_items
    try:
        if market_articles:
            save_news_items(market_articles)
    except Exception:
        logger.warning("Failed to persist market-sentiment articles to DB", exc_info=True)

    _market_cache = result
    _market_cache_ts = now
    result["cached"] = False
    return result


@router.get("/source-freshness")
async def get_source_freshness(
    auth: dict = Depends(require_auth),
):
    """Return per-source freshness status and 24h article counts.

    Response:
        {source_id: {fresh: bool|null, last_update: str|null, count_24h: int, label: str, category: str, ttl_seconds: int}}

    fresh=true  → data within TTL
    fresh=false → data exists but stale
    fresh=null  → never fetched / source unavailable
    """
    from src.db.sentiment_store import get_source_freshness as _db_freshness
    return {"sources": _db_freshness()}


@router.get("/stream")
async def news_stream(request: Request, symbol: str = Query("")):
    """SSE stream for real-time news updates with sentiment scoring.

    Accepts optional `?symbol=` query param for per-stock streaming.
    Runs a background polling loop that fetches+scores news periodically
    and pushes them to connected clients via SSEBus pub/sub.

    Usage (frontend):
        const es = new EventSource("/v1/news/stream?symbol=000001.SZ");
        es.addEventListener("news", (e) => { ... });  // new scored article
    """
    from src.services.sse_bus import get_sse_bus
    from backtest.loaders.news import NewsFetcher

    bus = get_sse_bus()
    channel = f"news:stream:symbol:{symbol.upper()}" if symbol else "news:stream:market"
    seen_urls: set[str] = set()
    fetcher = NewsFetcher()
    analyzer = SentimentAnalyzer()
    stop_event = asyncio.Event()

    async def poll_loop():
        """Fetch news on an interval, score, and publish."""
        from src.db.sentiment_store import save_news_items as _save

        # Initial fetch immediately
        try:
            if symbol:
                raw = fetcher.fetch_stock_news(symbol.strip().upper(), max_results=10)
            else:
                raw = fetcher.fetch_market_news(max_results=10)

            batch: list[dict] = []
            for item in raw:
                url = item.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                text = f"{item.get('title', '')} {item.get('summary', item.get('snippet', ''))}"
                score = analyzer.analyze_text(text)
                label = "positive" if score > 0.6 else ("negative" if score < 0.4 else "neutral")
                article = {
                    "title": item.get("title", ""),
                    "url": url,
                    "source": item.get("source", "web_search"),
                    "source_label": item.get("source_label", item.get("source", "")),
                    "summary": (item.get("summary", "") or item.get("snippet", ""))[:200],
                    "published_at": item.get("published_at", ""),
                    "sentiment_score": score,
                    "sentiment_label": label,
                }
                batch.append(article)
                await bus.publish(channel, "news", article)
            # Persist to DB (fire-and-forget)
            if batch:
                try:
                    _save(batch)
                except Exception:
                    logger.warning("SSE stream: failed to persist initial batch", exc_info=True)
        except Exception as e:
            logger.warning("Initial news poll for stream failed: %s", e)

        # Subsequent polls on interval
        while not stop_event.is_set():
            try:
                await asyncio.sleep(30)  # poll every 30s
                if stop_event.is_set():
                    break
                if symbol:
                    raw = fetcher.fetch_stock_news(symbol.strip().upper(), max_results=5)
                else:
                    raw = fetcher.fetch_market_news(max_results=5)

                batch = []
                for item in raw:
                    url = item.get("url", "")
                    if url and url in seen_urls:
                        continue
                    if url:
                        seen_urls.add(url)
                    text = f"{item.get('title', '')} {item.get('summary', item.get('snippet', ''))}"
                    score = analyzer.analyze_text(text)
                    label = "positive" if score > 0.6 else ("negative" if score < 0.4 else "neutral")
                    article = {
                        "title": item.get("title", ""),
                        "url": url,
                        "source": item.get("source", "web_search"),
                        "source_label": item.get("source_label", item.get("source", "")),
                        "summary": (item.get("summary", "") or item.get("snippet", ""))[:200],
                        "published_at": item.get("published_at", ""),
                        "sentiment_score": score,
                        "sentiment_label": label,
                    }
                    batch.append(article)
                    await bus.publish(channel, "news", article)
                # Persist to DB (fire-and-forget)
                if batch:
                    try:
                        _save(batch)
                    except Exception:
                        logger.warning("SSE stream: failed to persist poll batch", exc_info=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("News poll failed in stream: %s", e)

    poll_task = asyncio.create_task(poll_loop())

    async def event_generator():
        try:
            async for event in bus.subscribe(channel, heartbeat_interval=15.0):
                if await request.is_disconnected():
                    break
                if event["type"] == "news":
                    # Strip internal fields (type, ts) from the payload
                    payload = {k: v for k, v in event.items() if k not in ("type", "ts")}
                    yield f"event: news\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                elif event["type"] == "heartbeat":
                    yield f": heartbeat\n\n"
        finally:
            stop_event.set()
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
