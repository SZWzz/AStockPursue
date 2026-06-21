"""News sentiment analysis service.

Chinese NLP sentiment scoring with SnowNLP.
Individual stock sentiment aggregation and trending topic extraction.
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SentimentResult(BaseModel):
    title: str
    url: str = ""
    source: str = ""
    summary: str = ""
    published_at: str = ""
    sentiment_score: float = 0.5  # 0=negative, 1=positive
    sentiment_label: str = "neutral"  # positive/neutral/negative
    matched_symbols: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class StockSentiment(BaseModel):
    symbol: str
    sentiment_mean: float = 0.5
    sentiment_std: float = 0.0
    news_count: int = 0
    trending_score: float = 0.0


class TopicScore(BaseModel):
    topic: str
    count: int
    sentiment_mean: float
    trending_score: float


class SentimentAnalyzer:
    """Chinese financial news sentiment analyzer."""

    def analyze_text(self, text: str) -> float:
        """Score a single text (0=negative, 1=positive)."""
        if not text or not text.strip():
            return 0.5

        try:
            from snownlp import SnowNLP
            s = SnowNLP(text)
            return round(float(s.sentiments), 4)
        except ImportError:
            # Fallback: keyword-based sentiment
            pos_words = ["涨", "涨停", "利好", "增长", "突破", "盈利", "买入", "增持", "业绩", "反转"]
            neg_words = ["跌", "跌停", "利空", "下滑", "亏损", "卖出", "减持", "风险", "调查", "处罚"]
            pos_count = sum(1 for w in pos_words if w in text)
            neg_count = sum(1 for w in neg_words if w in text)
            total = pos_count + neg_count
            if total == 0:
                return 0.5
            return round(pos_count / total, 4)

    def aggregate_by_stock(self, results: list[SentimentResult]) -> dict[str, StockSentiment]:
        """Aggregate sentiment results by stock symbol."""
        stock_data: dict[str, list[float]] = {}
        for r in results:
            for sym in r.matched_symbols:
                stock_data.setdefault(sym, []).append(r.sentiment_score)

        return {
            sym: StockSentiment(
                symbol=sym,
                sentiment_mean=round(float(np.mean(scores)), 4),
                sentiment_std=round(float(np.std(scores, ddof=1)), 4) if len(scores) > 1 else 0.0,
                news_count=len(scores),
                trending_score=round(float(np.mean(scores)) * min(1.0, len(scores) / 10), 4),
            )
            for sym, scores in stock_data.items()
        }

    def trending_topics(self, results: list[SentimentResult], top_n: int = 10) -> list[TopicScore]:
        """Extract trending topics with sentiment-weighted scores."""
        topic_counter: Counter[str] = Counter()
        topic_sentiments: dict[str, list[float]] = {}

        for r in results:
            for topic in r.topics:
                topic_counter[topic] += 1
                topic_sentiments.setdefault(topic, []).append(r.sentiment_score)

        topics: list[TopicScore] = []
        for topic, count in topic_counter.most_common(top_n * 2):
            scores = topic_sentiments.get(topic, [0.5])
            topics.append(TopicScore(
                topic=topic,
                count=count,
                sentiment_mean=round(float(np.mean(scores)), 4),
                trending_score=round(count * float(np.mean(scores)), 2),
            ))

        topics.sort(key=lambda x: x.trending_score, reverse=True)
        return topics[:top_n]
