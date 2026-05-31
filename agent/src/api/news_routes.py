"""News Sentiment REST API."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

# Mock news data for demo
_MOCK_NEWS = [
    {"title": "央行宣布降准0.5个百分点 释放长期资金约1万亿", "source": "eastmoney", "url": "", "summary": "中国人民银行决定下调金融机构存款准备金率0.5个百分点", "published_at": "2024-01-15T09:00:00", "sentiment_score": 0.72, "sentiment_label": "positive", "matched_symbols": ["000001.SZ", "600036.SH"], "topics": ["降准", "银行", "货币政策"]},
    {"title": "宁德时代发布新一代钠离子电池 能量密度突破200Wh/kg", "source": "cls", "url": "", "summary": "宁德时代在技术发布会上展示了新一代钠离子电池产品", "published_at": "2024-01-15T10:30:00", "sentiment_score": 0.85, "sentiment_label": "positive", "matched_symbols": ["300750.SZ"], "topics": ["钠离子电池", "新能源"]},
    {"title": "恒瑞医药PD-1单抗获FDA突破性疗法认定", "source": "tonghuashun", "url": "", "summary": "恒瑞医药宣布其PD-1单克隆抗体获美国FDA突破性疗法认定", "published_at": "2024-01-15T11:00:00", "sentiment_score": 0.91, "sentiment_label": "positive", "matched_symbols": ["600276.SH"], "topics": ["创新药", "FDA"]},
    {"title": "贵州茅台预计2024年净利润同比增长约15%", "source": "eastmoney", "url": "", "summary": "贵州茅台发布业绩预告，预计2024年实现归母净利润约857亿元", "published_at": "2024-01-15T08:30:00", "sentiment_score": 0.65, "sentiment_label": "positive", "matched_symbols": ["600519.SH"], "topics": ["白酒", "业绩预告"]},
    {"title": "两市成交额连续5日突破万亿 北向资金净流入超百亿", "source": "eastmoney", "url": "", "summary": "A股市场交投活跃，沪深两市成交额连续第五个交易日突破1万亿元", "published_at": "2024-01-15T15:30:00", "sentiment_score": 0.68, "sentiment_label": "positive", "matched_symbols": [], "topics": ["成交额", "北向资金"]},
    {"title": "多家房企发布债务展期公告 行业流动性压力持续", "source": "cls", "url": "", "summary": "多家房地产企业近期发布债务展期公告，显示行业整体流动性压力仍然较大", "published_at": "2024-01-15T14:00:00", "sentiment_score": 0.18, "sentiment_label": "negative", "matched_symbols": ["000002.SZ"], "topics": ["房地产", "债务"]},
    {"title": "比亚迪1月新能源汽车销量同比增长33%", "source": "tonghuashun", "url": "", "summary": "比亚迪公告称1月新能源汽车销量为20.1万辆，同比增长33.1%", "published_at": "2024-01-15T16:00:00", "sentiment_score": 0.78, "sentiment_label": "positive", "matched_symbols": ["002594.SZ"], "topics": ["新能源汽车", "销量"]},
    {"title": "ST公司退市风险警示密集发布 投资者需警惕", "source": "eastmoney", "url": "", "summary": "近期多家ST公司密集发布退市风险警示公告", "published_at": "2024-01-15T13:00:00", "sentiment_score": 0.22, "sentiment_label": "negative", "matched_symbols": [], "topics": ["ST", "退市"]},
]


@router.get("/feed")
async def get_news_feed(
    symbol: str = "",
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(require_auth),
):
    """Get latest news with sentiment scores."""
    news = _MOCK_NEWS
    if symbol:
        news = [n for n in news if symbol.upper() in [s.upper() for s in n.get("matched_symbols", [])]]
        if not news:
            news = [dict(n, matched_symbols=[symbol]) for n in _MOCK_NEWS[:3]]

    return {"articles": news[:limit], "total": len(news[:limit]), "symbol": symbol or "market"}


@router.get("/sentiment/{symbol}")
async def get_stock_sentiment(symbol: str, auth: dict = Depends(require_auth)):
    """Get sentiment history and aggregate for a stock."""
    stock_news = [n for n in _MOCK_NEWS if symbol.upper() in [s.upper() for s in n.get("matched_symbols", [])]]
    if not stock_news:
        stock_news = [dict(n, matched_symbols=[symbol]) for n in _MOCK_NEWS[:3]]

    scores = [n.get("sentiment_score", 0.5) for n in stock_news]
    import numpy as np
    return {
        "symbol": symbol,
        "sentiment_mean": round(float(np.mean(scores)), 4) if scores else 0.5,
        "sentiment_std": round(float(np.std(scores, ddof=1)), 4) if len(scores) > 1 else 0.0,
        "news_count": len(stock_news),
        "trending_score": round(float(np.mean(scores)) * min(1.0, len(scores) / 10), 4) if scores else 0.0,
        "recent_articles": stock_news[:10],
    }


@router.get("/trending")
async def get_trending_topics(limit: int = 10, auth: dict = Depends(require_auth)):
    """Get trending topics with sentiment aggregation."""
    from collections import Counter
    import numpy as np

    topic_counter: Counter[str] = Counter()
    topic_sents: dict[str, list[float]] = {}
    for n in _MOCK_NEWS:
        for t in n.get("topics", []):
            topic_counter[t] += 1
            topic_sents.setdefault(t, []).append(n.get("sentiment_score", 0.5))

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
    return {"topics": topics[:limit]}


@router.get("/stream")
async def news_stream(request: Request):
    """SSE stream for real-time news updates (demo)."""
    async def event_stream():
        for i, news in enumerate(_MOCK_NEWS[:5]):
            if await request.is_disconnected():
                break
            yield f"event: news\ndata: {json.dumps(news, ensure_ascii=False)}\n\n"
            await asyncio.sleep(1.5)
        yield f"event: done\ndata: {{\"ts\": \"{datetime.now(timezone.utc).isoformat()}\"}}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
