"""C4 Dashboard aggregation API — Phase C P3.

Single endpoint that aggregates data from all 8 modules in parallel,
with 5s timeout and graceful degradation per module.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from src.auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Module fetchers (each returns a dict or None on failure)
# ---------------------------------------------------------------------------

async def _fetch_market_overview() -> dict[str, Any] | None:
    """Market indices snapshot — uses Tencent real-time quote API.

    The Tencent API supports A-share index codes natively (e.g.
    ``sh000300`` for CSI300).  DataStore OHLCV loaders don't handle
    index codes, so we fetch live quotes directly.
    """
    try:
        import requests

        # Tencent API index code mapping
        index_map = [
            ("sh000300", "沪深300"),
            ("sh000905", "中证500"),
            ("sz399006", "创业板指"),
        ]
        codes = ",".join(c for c, _ in index_map)
        url = f"https://qt.gtimg.cn/q={codes}"
        resp = requests.get(url, timeout=5, headers={"Referer": "https://qt.gtimg.cn/"})
        resp.encoding = "gbk"

        result = []
        for qt_code, name in index_map:
            price = 0.0
            change_pct = 0.0
            try:
                text = resp.text or ""
                # Tencent returns one line per code: v_sh000300="1~沪深300~3892.50~..."
                marker = f'v_{qt_code}="'
                idx = text.index(marker) + len(marker)
                end = text.index('"', idx)
                parts = text[idx:end].split("~")
                if len(parts) >= 4:
                    price = float(parts[3])   # current price
                    prev_close = float(parts[4]) if len(parts) > 4 else price
                    if prev_close > 0:
                        change_pct = round((price / prev_close - 1) * 100, 2)
            except Exception:
                pass
            result.append({"name": name, "code": qt_code, "price": price, "change_pct": change_pct})

        return {"indices": result, "vix": None, "fear_greed": None}
    except Exception as exc:
        logger.debug("_fetch_market_overview failed: %s", exc)
        return None


async def _fetch_datasource_health() -> dict[str, Any] | None:
    """Data source availability snapshot."""
    try:
        from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered

        _ensure_registered()
        sources = []
        for name, cls in sorted(LOADER_REGISTRY.items()):
            try:
                instance = cls()
                available = instance.is_available() if hasattr(instance, "is_available") else True
            except Exception:
                available = False
            sources.append({
                "name": name,
                "markets": list(getattr(cls, "markets", set())),
                "requires_auth": getattr(cls, "requires_auth", False),
                "available": available,
            })

        available_count = sum(1 for s in sources if s["available"])
        return {
            "sources": sources,
            "available_count": available_count,
            "total_count": len(sources),
            "cache_hit_rate": None,
            "api_calls_today": None,
        }
    except Exception as exc:
        logger.debug("_fetch_datasource_health failed: %s", exc)
        return None


async def _fetch_sentiment_overview() -> dict[str, Any] | None:
    """Market sentiment snapshot — fetches recent news and scores them.

    Tries cached DB news first, falls back to a quick DuckDuckGo search
    for Chinese financial headlines so the dashboard card is never blank.
    """
    try:
        from src.services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()

        articles: list[dict[str, Any]] = []
        # Try DB cache first
        try:
            from src.db.sentiment_store import get_recent_news
            articles = list(get_recent_news(limit=20, hours=48))
        except Exception:
            pass

        # Fallback: quick web search for recent financial headlines
        if not articles:
            try:
                import requests
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.news("A股 股市", max_results=8))
                for r in raw:
                    articles.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source": r.get("source", ""),
                        "published_at": r.get("date", ""),
                    })
            except Exception:
                pass

        if not articles:
            return {"overall_sentiment": None, "sentiment_label": None, "trend": None,
                    "trending_topics": [], "recent_headlines": []}

        scores = []
        headlines = []
        for a in articles:
            title = a.get("title", "")
            if title:
                score = analyzer.analyze_text(title)
                scores.append(score)
                headlines.append(title)

        if not scores:
            return {"overall_sentiment": None, "sentiment_label": None, "trend": None,
                    "trending_topics": [], "recent_headlines": []}

        avg_score = round(sum(scores) / len(scores), 2)

        # Extract trending topics via the analyzer's built-in method
        from src.services.sentiment_analyzer import SentimentResult
        dummy_results = [SentimentResult(title=h, sentiment_score=s) for h, s in zip(headlines, scores)]
        topic_list = analyzer.trending_topics(dummy_results, top_n=5)
        topics = [{"topic": t.topic, "count": t.count} for t in topic_list]

        return {
            "overall_sentiment": avg_score,
            "sentiment_label": "偏乐观" if avg_score > 0.55 else ("偏悲观" if avg_score < 0.45 else "中性"),
            "trend": "stable",
            "trending_topics": topics,
            "recent_headlines": headlines[:5],
        }
    except Exception as exc:
        logger.debug("_fetch_sentiment_overview failed: %s", exc)
        return None


async def _fetch_papertrading_runtime(user_id: int) -> dict[str, Any] | None:
    """Active paper trading strategies with live P&L."""
    try:
        from papertrade.repository import PaperTradeRepository

        repo = PaperTradeRepository()
        rows = repo.list_runs(user_id=user_id, limit=20)

        strategies = []
        for r in rows:
            config = r.get("config", {})
            initial_cap = float(config.get("initial_capital", 100_000))
            current_cap = float(r.get("current_capital", initial_cap))
            total_return_pct = ((current_cap - initial_cap) / initial_cap * 100) if initial_cap > 0 else 0.0

            positions = repo.get_positions(r["id"])
            position_codes = [p.get("symbol", "") for p in positions]

            strategies.append({
                "name": r.get("run_name", r["id"][:12]),
                "status": r.get("status", "unknown"),
                "total_return_pct": round(total_return_pct, 2),
                "sharpe": None,
                "daily_pnl_pct": None,
                "max_drawdown_pct": None,
                "positions": position_codes,
            })

        return {
            "strategies": strategies,
            "count": len(strategies),
        }
    except Exception as exc:
        logger.debug("_fetch_papertrading_runtime failed: %s", exc)
        return None


async def _fetch_factor_pipeline(user_id: int) -> dict[str, Any] | None:
    """Factor pipeline status: mining → candidates → zoo → production."""
    try:
        from src.factors.mining.factor_kb import get_kb

        kb = get_kb(user_id=user_id)
        guidance = kb.get_mining_guidance()
        all_entries = kb.list_all()

        # Count active GP runs from the job registry
        active_gp_runs = 0
        try:
            from src.api.factor_mining_routes import _jobs
            active_gp_runs = sum(1 for j in _jobs.values() if j.get("status") == "running")
        except Exception:
            pass

        # Real candidate breakdown from KB
        status_counts: dict[str, int] = {}
        for e in all_entries:
            s = e.status or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "mining": {
                "active_gp_runs": active_gp_runs,
                "active_llm_agents": 0,
            },
            "candidates": {
                "pending_validation": status_counts.get("discovered", 0) + status_counts.get("validating", 0),
                "pending_review": status_counts.get("validating", 0),
                "passed": status_counts.get("approved", 0) + status_counts.get("production", 0),
                "redundant": status_counts.get("deprecated", 0) + status_counts.get("archived", 0),
            },
            "zoo": {
                "total_factors": len(all_entries),
                "themes": len(guidance.get("theme_health", {})),
                "alive": guidance.get("total_active", 0),
                "reversed": status_counts.get("deprecated", 0),
                "dead": guidance.get("total_dead", 0),
            },
            "theme_health": guidance.get("theme_health", {}),
        }
    except Exception as exc:
        logger.debug("_fetch_factor_pipeline failed: %s", exc)
        return None


async def _fetch_factor_lab(user_id: int) -> dict[str, Any] | None:
    """Factor lab: recent discoveries from KB."""
    try:
        from src.factors.mining.factor_kb import get_kb

        kb = get_kb(user_id=user_id)
        recent = sorted(kb.list_all(), key=lambda e: e.discovered_at, reverse=True)[:5]
        return {
            "recent_discoveries": [
                {"alpha_id": e.alpha_id, "formula": e.formula[:60], "test_ic": e.test_ic, "status": e.status}
                for e in recent
            ],
        }
    except Exception as exc:
        logger.debug("_fetch_factor_lab failed: %s", exc)
        return None


_active_events: list[dict[str, str]] = []


def log_activity(event: str, user_id: int | None = None) -> None:
    """Record a dashboard activity event (in-memory, recent only)."""
    timestamp = datetime.now().strftime("%H:%M")
    prefix = f"[user:{user_id}] " if user_id else ""
    _active_events.insert(0, {"time": timestamp, "event": f"{prefix}{event}"})
    # Keep at most 30 most-recent events
    while len(_active_events) > 30:
        _active_events.pop()


async def _fetch_recent_activity(user_id: int) -> dict[str, Any] | None:
    """Recent system activity feed — augmented with live paper-trading events."""
    try:
        events = list(_active_events)

        # Augment with real paper trading status changes
        try:
            from papertrade.repository import PaperTradeRepository
            repo = PaperTradeRepository()
            rows = repo.list_runs(user_id=user_id, limit=5)
            for r in rows:
                status = r.get("status", "")
                name = r.get("run_name", r["id"][:12])
                if status == "running":
                    last_bar = r.get("last_bar_time", "")
                    if last_bar:
                        events.append({
                            "time": str(last_bar)[-8:-3] if len(str(last_bar)) >= 8 else "",
                            "event": f"模拟盘 {name} 运行中 @ {last_bar}",
                        })
        except Exception:
            pass

        # Sort by time descending and deduplicate roughly
        seen = set()
        deduped = []
        for e in sorted(events, key=lambda x: x["time"], reverse=True):
            key = e["time"] + e["event"]
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        return {"events": deduped[:20]}
    except Exception as exc:
        logger.debug("_fetch_recent_activity failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Aggregate endpoint
# ---------------------------------------------------------------------------

@router.get("/overview")
async def dashboard_overview(
    user_id: int | None = None,
    auth: dict = Depends(require_auth),
) -> dict[str, Any]:
    """Aggregate all dashboard data in one request.

    8 modules are fetched in parallel with 5s timeout each.
    Failed modules return None — frontend handles graceful degradation.
    """
    uid = user_id or int(auth.get("user_id", 1))

    async def _safe_fetch(name: str, coro):
        try:
            return await asyncio.wait_for(coro, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Dashboard module '%s' timed out", name)
            return None
        except Exception as exc:
            logger.debug("Dashboard module '%s' failed: %s", name, exc)
            return None

    results = await asyncio.gather(
        _safe_fetch("market", _fetch_market_overview()),
        _safe_fetch("datasource", _fetch_datasource_health()),
        _safe_fetch("sentiment", _fetch_sentiment_overview()),
        _safe_fetch("papertrading", _fetch_papertrading_runtime(uid)),
        _safe_fetch("pipeline", _fetch_factor_pipeline(uid)),
        _safe_fetch("lab", _fetch_factor_lab(uid)),
        _safe_fetch("activity", _fetch_recent_activity(uid)),
    )

    return {
        "market": results[0],
        "datasource": results[1],
        "sentiment": results[2],
        "papertrading": results[3],
        "pipeline": results[4],
        "lab": results[5],
        "activity": results[6],
    }
