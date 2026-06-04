"""Sentiment analysis nodes — news sentiment scoring and macro sentiment indicators."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class NewsSentimentNode(BaseNode):
    node_type = "news_sentiment"; category = "data"; label = "News Sentiment"
    description = (
        "Analyse sentiment of news articles or text using SnowNLP or keyword-based scoring. "
        "Aggregate scores by stock symbol or extract trending topics."
    )
    icon = "Newspaper"
    resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("news_data", PortType.ANY,
                         description="News data: list of {'text', 'symbol', 'source'} dicts, or list of strings"),
    ]
    outputs = [
        BaseNode.out_port("sentiment", PortType.SENTIMENT,
                          description="Sentiment scores per stock or topic"),
    ]
    config_schema = {
        "method": {
            "title": "Method", "type": "string",
            "enum": ["snownlp", "keyword", "auto"], "default": "auto",
            "description": "auto = try SnowNLP, fall back to keyword",
        },
        "aggregate_by": {
            "title": "Aggregate By", "type": "string",
            "enum": ["stock", "topic", "none"], "default": "stock",
        },
        "top_n_topics": {
            "title": "Top N Topics", "type": "integer", "default": 10,
            "minimum": 1, "maximum": 50,
        },
        "min_articles": {
            "title": "Min Articles", "type": "integer", "default": 3,
            "description": "Minimum articles for a stock to be included in aggregation",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        news_data = inputs.get("news_data")
        if news_data is None:
            return {"sentiment": {"error": "No news data provided", "scores": {}, "topics": []}}

        method = config.get("method", "auto")
        aggregate_by = config.get("aggregate_by", "stock")
        top_n = int(config.get("top_n_topics", 10))
        min_articles = int(config.get("min_articles", 3))

        # ── Normalise input ───────────────────────────────────────────────────
        articles: List[Dict[str, Any]] = []
        if isinstance(news_data, list):
            for item in news_data:
                if isinstance(item, str):
                    articles.append({"text": item})
                elif isinstance(item, dict):
                    articles.append(item)
        elif isinstance(news_data, dict):
            # Could be {"articles": [...]} or {"text": "..."}
            if "articles" in news_data:
                articles = news_data["articles"]
            elif "text" in news_data:
                articles = [news_data]
        elif isinstance(news_data, str):
            articles = [{"text": news_data}]

        if not articles:
            return {"sentiment": {"error": "Could not parse news data", "scores": {}, "topics": []}}

        # ── Score each article ────────────────────────────────────────────────
        scores: List[Dict[str, Any]] = []
        use_snownlp = method in ("snownlp", "auto")

        for art in articles:
            text = str(art.get("text", art.get("content", "")))
            if not text.strip():
                continue
            score = self._score_text(text, use_snownlp=use_snownlp)
            scores.append({
                "symbol": art.get("symbol", art.get("stock", "")),
                "source": art.get("source", ""),
                "text_preview": text[:120],
                "sentiment": score,
            })

        if not scores:
            return {"sentiment": {"scores": {}, "topics": [], "note": "No valid articles"}}

        # ── Aggregate by stock ────────────────────────────────────────────────
        stock_scores: Dict[str, Dict[str, Any]] = {}
        if aggregate_by in ("stock", "topic"):
            for s in scores:
                sym = s["symbol"] or "_unknown"
                if sym not in stock_scores:
                    stock_scores[sym] = {"count": 0, "total": 0.0, "values": []}
                stock_scores[sym]["count"] += 1
                stock_scores[sym]["total"] += s["sentiment"]
                stock_scores[sym]["values"].append(s["sentiment"])

            # Filter by min_articles
            stock_scores = {
                k: {
                    "count": v["count"],
                    "mean_sentiment": round(v["total"] / v["count"], 4),
                    "std_sentiment": round(float(np.std(v["values"])), 4) if len(v["values"]) > 1 else 0.0,
                }
                for k, v in stock_scores.items() if v["count"] >= min_articles and k != "_unknown"
            }

        result: Dict[str, Any] = {
            "scores": stock_scores,
            "n_articles": len(scores),
            "overall_mean": round(float(np.mean([s["sentiment"] for s in scores])), 4) if scores else None,
        }

        # ── Trending topics (simple keyword frequency) ────────────────────────
        if aggregate_by == "topic":
            topics = self._extract_topics(scores, top_n=top_n)
            result["topics"] = topics

        logger.info("NewsSentiment: %d articles → %d stocks, mean=%.3f",
                     len(scores), len(stock_scores), result["overall_mean"] or 0)
        return {"sentiment": result}

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _score_text(text: str, use_snownlp: bool = True) -> float:
        """Score a single text 0=negative, 1=positive."""
        if use_snownlp:
            try:
                from snownlp import SnowNLP
                return float(SnowNLP(text).sentiments)
            except (ImportError, Exception):
                pass

        # Keyword fallback
        pos_words = ["涨", "利好", "突破", "增长", "上升", "盈利", "买入", "增持", "反弹", "牛市",
                      "bullish", "upgrade", "beat", "growth", "profit"]
        neg_words = ["跌", "利空", "下跌", "亏损", "下滑", "风险", "卖出", "减持", "崩盘", "熊市",
                      "bearish", "downgrade", "miss", "decline", "loss"]
        text_lower = text.lower()
        pos_count = sum(1 for w in pos_words if w in text_lower)
        neg_count = sum(1 for w in neg_words if w in text_lower)
        total = pos_count + neg_count
        if total == 0:
            return 0.5
        return pos_count / total

    @staticmethod
    def _extract_topics(scores: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
        """Simple keyword-based topic extraction."""
        topic_keywords = {
            "货币政策": ["央行", "利率", "降息", "加息", "流动性", "准备金"],
            "财报业绩": ["财报", "利润", "营收", "净利润", "业绩", "增长"],
            "行业政策": ["政策", "监管", "发改委", "工信部", "文件"],
            "国际市场": ["美股", "港股", "美联储", "美元", "原油"],
            "科技创新": ["AI", "人工智能", "芯片", "新能源", "5G", "半导体"],
            "资金流向": ["北向", "外资", "机构", "主力", "游资"],
            "并购重组": ["重组", "收购", "合并", "注入", "借壳"],
        }
        topic_hits: Dict[str, Dict[str, Any]] = {}
        for s in scores:
            text = s.get("text_preview", "")
            sym = s.get("symbol", "")
            for topic, kws in topic_keywords.items():
                if any(kw in text for kw in kws):
                    if topic not in topic_hits:
                        topic_hits[topic] = {"name": topic, "count": 0, "sentiment_total": 0.0, "symbols": set()}
                    topic_hits[topic]["count"] += 1
                    topic_hits[topic]["sentiment_total"] += s["sentiment"]
                    if sym:
                        topic_hits[topic]["symbols"].add(sym)

        topics = []
        for t in sorted(topic_hits.values(), key=lambda x: x["count"], reverse=True)[:top_n]:
            topics.append({
                "name": t["name"],
                "article_count": t["count"],
                "mean_sentiment": round(t["sentiment_total"] / t["count"], 4),
                "heat_score": round(t["count"] * (1 + abs(0.5 - t["sentiment_total"] / t["count"])), 2),
            })
        return topics


@register_node
class MacroSentimentNode(BaseNode):
    node_type = "macro_sentiment"; category = "data"; label = "Macro Sentiment"
    description = (
        "Fetch macro market sentiment indicators: VIX, DXY, yield curve spread, "
        "and Fear & Greed Index."
    )
    icon = "Globe"
    resource_profile = "io_bound"
    inputs: List[NodePort] = []
    outputs = [
        BaseNode.out_port("macro_data", PortType.PARAMS,
                          description="Dict of macro sentiment indicators"),
    ]
    config_schema = {
        "indicators": {
            "title": "Indicators", "type": "string",
            "enum": ["all", "vix", "dxy", "fear_greed", "yield_curve"],
            "default": "all",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        wanted = config.get("indicators", "all")
        result: Dict[str, Any] = {}

        try:
            from src.tools.sentiment_tool import MarketSentimentTool
            tool = MarketSentimentTool()
            data = tool.fetch_all() if wanted == "all" else tool.fetch_indicators(wanted)
            result = data if isinstance(data, dict) else {"raw": str(data)}
        except ImportError:
            # Fallback: use backtest.loaders.sentiment directly
            try:
                from backtest.loaders.sentiment import SentimentFetcher
                fetcher = SentimentFetcher()
                if wanted in ("all", "vix"):
                    result["vix"] = fetcher.get_vix()
                if wanted in ("all", "dxy"):
                    result["dxy"] = fetcher.get_dxy()
                if wanted in ("all", "yield_curve"):
                    result["yield_curve"] = fetcher.get_yield_curve()
                if wanted in ("all", "fear_greed"):
                    result["fear_greed"] = fetcher.get_fear_greed()
            except (ImportError, Exception) as e:
                result["error"] = str(e)
                result["note"] = "Sentiment fetcher unavailable"

        # ── Derive composite signal ───────────────────────────────────────────
        signal = self._derive_signal(result)
        result["composite_signal"] = signal

        logger.info("MacroSentiment: composite=%s", signal)
        return {"macro_data": result}

    @staticmethod
    def _derive_signal(data: dict) -> str:
        """Derive a simple bull/bear/neutral signal from indicators."""
        bullish = 0
        bearish = 0

        vix = data.get("vix")
        if vix is not None:
            vix_val = float(vix) if not isinstance(vix, dict) else float(vix.get("value", 20))
            if vix_val < 15:
                bullish += 1
            elif vix_val > 25:
                bearish += 1

        dxy = data.get("dxy")
        if dxy is not None:
            dxy_val = float(dxy) if not isinstance(dxy, dict) else float(dxy.get("value", 100))
            if dxy_val > 105:
                bearish += 1  # Strong dollar = EM pressure
            elif dxy_val < 95:
                bullish += 1

        fg = data.get("fear_greed")
        if fg is not None:
            fg_val = float(fg) if not isinstance(fg, dict) else float(fg.get("value", 50))
            if fg_val > 70:
                bullish += 1
            elif fg_val < 30:
                bearish += 1

        yc = data.get("yield_curve")
        if yc is not None:
            yc_val = float(yc) if not isinstance(yc, dict) else float(yc.get("spread", 0))
            if yc_val < 0:
                bearish += 1  # Inverted = recession signal

        if bullish > bearish:
            return "bullish"
        elif bearish > bullish:
            return "bearish"
        return "neutral"
