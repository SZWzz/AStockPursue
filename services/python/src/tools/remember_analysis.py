"""Remember Analysis tool — record AI agent analysis decisions for later validation.

This tool writes to the analysis_memory table so the ReflectionWorker can
later verify whether the agent's directional call was correct.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agent.tools import BaseTool

logger = logging.getLogger(__name__)


class RememberAnalysisTool(BaseTool):
    """Record an analysis decision for future reflection and learning.

    The ReflectionWorker will validate this decision after a holding period
    (default 7 days) by comparing actual returns against the predicted direction.
    """

    name: str = "remember_analysis"
    description: str = (
        "Record this analysis decision for future reflection and learning. "
        "The system will later validate whether your prediction was correct."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock/crypto symbol (e.g. 600519.SH, BTC-USDT)",
            },
            "decision": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
                "description": "Your directional prediction",
            },
            "confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Confidence level (0-100)",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief summary of your reasoning",
            },
        },
        "required": ["symbol", "decision"],
    }
    is_readonly: bool = False  # Writes to the database

    def execute(self, symbol: str = "", decision: str = "neutral",
                confidence: int = 50, reasoning: str = "", **kwargs: Any) -> str:
        """Record the analysis decision to analysis_memory table.

        Args:
            symbol: Stock/crypto symbol.
            decision: bullish | bearish | neutral.
            confidence: 0-100 confidence level.
            reasoning: Brief summary of the reasoning.

        Returns:
            JSON with status and record id.
        """
        if not symbol:
            return json.dumps({"status": "error", "error": "symbol is required"}, ensure_ascii=False)

        if decision not in ("bullish", "bearish", "neutral"):
            return json.dumps({"status": "error", "error": f"Invalid decision: {decision!r}"}, ensure_ascii=False)

        try:
            from src.database import get_db
            db = get_db()
            if db is None:
                return json.dumps({
                    "status": "warning",
                    "message": "Database not available — analysis not persisted",
                    "symbol": symbol,
                    "decision": decision,
                }, ensure_ascii=False)

            # Try to get current price for the symbol
            price = 0.0
            try:
                from backtest.data_store import get_data_store
                store = get_data_store()
                from datetime import date
                today = date.today().isoformat()
                df = store.get_ohlcv(symbol, today, today, interval="1D")
                if df is not None and not df.empty:
                    price = float(df["close"].iloc[-1])
            except Exception:
                pass

            import asyncio
            now_str = __import__("datetime").datetime.now().isoformat()

            async def _insert():
                row = await db.fetchrow(
                    """
                    INSERT INTO analysis_memory
                        (user_id, symbol, decision, confidence, price_at_analysis,
                         reasoning, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    0,  # user_id 0 for system/agent
                    symbol,
                    decision,
                    confidence,
                    round(price, 4) if price > 0 else None,
                    reasoning[:2000] if reasoning else None,
                    now_str,
                )
                return row["id"] if row else None

            record_id = asyncio.get_event_loop().run_until_complete(_insert())

            logger.info("remember_analysis: symbol=%s decision=%s confidence=%d id=%s",
                         symbol, decision, confidence, record_id)

            return json.dumps({
                "status": "ok",
                "record_id": record_id,
                "symbol": symbol,
                "decision": decision,
                "confidence": confidence,
                "message": f"Analysis recorded: {decision} on {symbol} (confidence: {confidence}%)",
            }, ensure_ascii=False)

        except Exception as exc:
            logger.exception("remember_analysis failed")
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
