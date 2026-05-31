"""Sentiment / News persistence — read/write vt_news_items and vt_stock_sentiment.

Follows the free-functions pattern used by backtest_store.py and alpha_bench_store.py.
Each function opens its own connection; callers don't need to manage transactions.
"""

from __future__ import annotations

import logging
from typing import Any

from src.db.pool import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# News items
# ---------------------------------------------------------------------------


def save_news_items(articles: list[dict]) -> int:
    """Batch-insert news articles into vt_news_items.

    Uses ON CONFLICT (title, source) DO NOTHING to skip duplicates.
    Returns the number of rows actually inserted.
    """
    if not articles:
        return 0

    try:
        from psycopg2.extras import execute_values

        rows: list[tuple] = []
        for a in articles:
            rows.append((
                a.get("title", ""),
                a.get("url", ""),
                a.get("source", "web_search"),
                a.get("summary", "")[:500] if a.get("summary") else "",
                a.get("published_at", ""),
                a.get("sentiment_score", 0.5),
                a.get("sentiment_label", "neutral"),
                a.get("matched_symbols", []),
                a.get("topics", []),
            ))

        with get_connection() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """INSERT INTO vt_news_items
                       (title, url, source, summary, published_at,
                        sentiment_score, sentiment_label, matched_symbols, topics)
                       VALUES %s
                       ON CONFLICT (title, source) DO NOTHING""",
                    rows,
                    template="(%s, %s, %s, %s, %s::timestamptz, %s, %s, %s::text[], %s::text[])",
                )
                inserted = cur.rowcount
        logger.debug("Saved %d news items to DB (%d duplicates skipped)", inserted, len(articles) - inserted)
        return inserted
    except Exception:
        logger.warning("Failed to save news items to DB", exc_info=True)
        return 0


def get_recent_news(
    symbol: str = "",
    limit: int = 50,
    max_age_minutes: int = 30,
) -> list[dict[str, Any]]:
    """Return recent news articles from the database.

    If *symbol* is given, filters to articles whose matched_symbols array
    contains that symbol.  Otherwise returns market-wide news.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if symbol:
                    cur.execute(
                        """SELECT title, url, source, summary, published_at,
                                  sentiment_score, sentiment_label, matched_symbols, topics
                           FROM vt_news_items
                           WHERE published_at > now() - %s::interval
                             AND %s = ANY(matched_symbols)
                           ORDER BY published_at DESC
                           LIMIT %s""",
                        (f"{max_age_minutes} minutes", symbol.upper(), limit),
                    )
                else:
                    cur.execute(
                        """SELECT title, url, source, summary, published_at,
                                  sentiment_score, sentiment_label, matched_symbols, topics
                           FROM vt_news_items
                           WHERE published_at > now() - %s::interval
                           ORDER BY published_at DESC
                           LIMIT %s""",
                        (f"{max_age_minutes} minutes", limit),
                    )
                rows = cur.fetchall()

        articles: list[dict[str, Any]] = []
        for r in rows:
            articles.append({
                "title": r[0] or "",
                "url": r[1] or "",
                "source": r[2] or "web_search",
                "summary": (r[3] or "")[:200],
                "published_at": str(r[4]) if r[4] else "",
                "sentiment_score": float(r[5]) if r[5] is not None else 0.5,
                "sentiment_label": r[6] or "neutral",
            })
        return articles
    except Exception:
        logger.warning("Failed to query recent news from DB", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Stock sentiment
# ---------------------------------------------------------------------------


def save_stock_sentiment(
    symbol: str,
    date: str,
    sentiment_mean: float,
    sentiment_std: float,
    news_count: int,
    trending_score: float,
) -> bool:
    """Upsert daily stock sentiment into vt_stock_sentiment."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vt_stock_sentiment
                       (symbol, date, sentiment_mean, sentiment_std, news_count, trending_score)
                       VALUES (%s, %s::date, %s, %s, %s, %s)
                       ON CONFLICT (symbol, date)
                       DO UPDATE SET sentiment_mean = EXCLUDED.sentiment_mean,
                                     sentiment_std   = EXCLUDED.sentiment_std,
                                     news_count      = EXCLUDED.news_count,
                                     trending_score  = EXCLUDED.trending_score""",
                    (symbol.upper(), date, sentiment_mean, sentiment_std, news_count, trending_score),
                )
        return True
    except Exception:
        logger.warning("Failed to save stock sentiment for %s", symbol, exc_info=True)
        return False


def get_cached_news_by_source(
    source: str = "",
    symbol: str = "",
    max_age_minutes: int = 5,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return cached news from DB filtered by source and optional symbol.

    If the latest article for *source* is older than *max_age_minutes*,
    returns an empty list (caller should trigger a refresh).
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if symbol:
                    cur.execute(
                        """SELECT title, url, source, summary, published_at,
                                  sentiment_score, sentiment_label
                           FROM vt_news_items
                           WHERE published_at > now() - %s::interval
                             AND (%s = source OR %s = '')
                             AND %s = ANY(matched_symbols)
                           ORDER BY published_at DESC
                           LIMIT %s""",
                        (f"{max_age_minutes} minutes", source, source, symbol.upper(), limit),
                    )
                else:
                    cur.execute(
                        """SELECT title, url, source, summary, published_at,
                                  sentiment_score, sentiment_label
                           FROM vt_news_items
                           WHERE published_at > now() - %s::interval
                             AND (%s = source OR %s = '')
                           ORDER BY published_at DESC
                           LIMIT %s""",
                        (f"{max_age_minutes} minutes", source, source, limit),
                    )
                rows = cur.fetchall()

        articles: list[dict[str, Any]] = []
        for r in rows:
            articles.append({
                "title": r[0] or "",
                "url": r[1] or "",
                "source": r[2] or "web_search",
                "summary": (r[3] or "")[:200],
                "published_at": str(r[4]) if r[4] else "",
                "sentiment_score": float(r[5]) if r[5] is not None else 0.5,
                "sentiment_label": r[6] or "neutral",
            })
        return articles
    except Exception:
        logger.warning("Failed to query cached news by source from DB", exc_info=True)
        return []


def is_source_fresh(source: str, max_age_seconds: int = 300) -> bool:
    """Check whether the given source has fresh data in DB."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM vt_news_items
                       WHERE source = %s
                         AND published_at > now() - %s::interval
                       LIMIT 1""",
                    (source, f"{max_age_seconds} seconds"),
                )
                return cur.fetchone() is not None
    except Exception:
        logger.debug("is_source_fresh check failed for %s", source, exc_info=True)
        return False


def get_source_freshness() -> dict[str, dict[str, Any]]:
    """Return freshness + 24h count for all sources in DB.

    Returns:
        {source_id: {fresh: bool|null, last_update: str|null, count_24h: int}}
    """
    from backtest.loaders.news_sources.base import SOURCE_META, SOURCE_TTL

    result: dict[str, dict[str, Any]] = {}
    for src_id, meta in SOURCE_META.items():
        ttl = SOURCE_TTL.get(src_id, 300)
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Last update time
                    cur.execute(
                        """SELECT published_at FROM vt_news_items
                           WHERE source = %s
                           ORDER BY published_at DESC LIMIT 1""",
                        (src_id,),
                    )
                    last_row = cur.fetchone()
                    last_update = str(last_row[0]) if last_row else None

                    # Count in last 24h
                    cur.execute(
                        """SELECT COUNT(*) FROM vt_news_items
                           WHERE source = %s
                             AND created_at > now() - '24 hours'::interval""",
                        (src_id,),
                    )
                    count_row = cur.fetchone()
                    count_24h = int(count_row[0]) if count_row else 0

                # Determine freshness
                if last_update is None:
                    fresh = None  # never fetched
                else:
                    try:
                        from datetime import datetime, timezone
                        dt = datetime.fromisoformat(last_update.replace("+00:00", "").replace("Z", ""))
                        age = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).total_seconds()
                        fresh = age < ttl
                    except Exception:
                        fresh = False

                result[src_id] = {
                    "fresh": fresh,
                    "last_update": last_update,
                    "count_24h": count_24h,
                    "label": meta.get("label", src_id),
                    "category": meta.get("category", "market"),
                    "ttl_seconds": ttl,
                }
        except Exception:
            result[src_id] = {
                "fresh": None,
                "last_update": None,
                "count_24h": 0,
                "label": meta.get("label", src_id),
                "category": meta.get("category", "market"),
                "ttl_seconds": ttl,
            }

    return result


def get_stock_sentiment(symbol: str) -> dict[str, Any] | None:
    """Return the most recent stock sentiment record from the database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT symbol, date, sentiment_mean, sentiment_std, news_count, trending_score
                       FROM vt_stock_sentiment
                       WHERE symbol = %s
                       ORDER BY date DESC
                       LIMIT 1""",
                    (symbol.upper(),),
                )
                r = cur.fetchone()
        if not r:
            return None
        return {
            "symbol": r[0],
            "date": str(r[1]) if r[1] else "",
            "sentiment_mean": float(r[2]) if r[2] is not None else 0.5,
            "sentiment_std": float(r[3]) if r[3] is not None else 0.0,
            "news_count": int(r[4]) if r[4] is not None else 0,
            "trending_score": float(r[5]) if r[5] is not None else 0.0,
        }
    except Exception:
        logger.warning("Failed to query stock sentiment for %s from DB", symbol, exc_info=True)
        return None
