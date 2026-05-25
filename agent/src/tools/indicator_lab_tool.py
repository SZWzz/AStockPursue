"""Indicator Lab tool — lets the LLM agent create, search, and modify indicators.

Exposes the Indicator Lab repository to the agent loop so the agent can:
- Search for existing indicators
- Create new indicator code
- Modify and verify indicator code
- Promote mature indicators to Alpha Zoo factors
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agent.tools import BaseTool
from src.lab.params import IndicatorParamsParser, StrategyConfigParser
from src.lab.quality import analyze_indicator_code_quality
from src.lab.storage.repository import IndicatorRepository, _extract_meta_from_code
from src.security.sandbox import validate_code_safety

logger = logging.getLogger(__name__)


class IndicatorLabTool(BaseTool):
    """Agent tool for the Indicator Lab — create/search/modify indicators."""

    name = "indicator_lab"
    description = (
        "Create, search, modify, and manage trading indicator scripts in the "
        "Indicator Lab. Use this to help users prototype new strategies, fix "
        "indicator code, or promote proven indicators to Alpha Zoo factors."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "create", "modify", "verify", "promote", "delete"],
                "description": "Action to perform on the Indicator Lab",
            },
            "query": {
                "type": "string",
                "description": "Search query (for 'search' action) or indicator ID (for 'get', 'modify', 'verify', 'promote', 'delete')",
            },
            "code": {
                "type": "string",
                "description": "Python source code for 'create' or 'modify' actions",
            },
            "name": {
                "type": "string",
                "description": "Display name for new indicator (for 'create' action)",
            },
            "zoo_id": {
                "type": "string",
                "description": "Target zoo ID for promotion (default: 'user')",
            },
        },
        "required": ["action"],
    }
    repeatable = True
    is_readonly = False

    def __init__(self) -> None:
        self._repo = IndicatorRepository()

    def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "search":
                return self._search(kwargs.get("query", ""))
            elif action == "create":
                return self._create(
                    kwargs.get("code", ""),
                    kwargs.get("name", ""),
                )
            elif action == "modify":
                return self._modify(
                    kwargs.get("query", ""),
                    kwargs.get("code", ""),
                )
            elif action == "verify":
                return self._verify(kwargs.get("code", "") or kwargs.get("query", ""))
            elif action == "promote":
                return self._promote(
                    kwargs.get("query", ""),
                    kwargs.get("zoo_id", "user"),
                )
            elif action == "delete":
                return self._delete(kwargs.get("query", ""))
            else:
                return json.dumps({
                    "status": "error",
                    "error": f"Unknown action: {action}",
                })
        except Exception as e:
            logger.exception("IndicatorLabTool failed")
            return json.dumps({"status": "error", "error": str(e)})

    # ── internal actions ────────────────────────────────────────────────────

    def _search(self, query: str) -> str:
        all_items = self._repo.list()

        if not query:
            results = all_items
        else:
            q = query.lower()
            results = [
                i for i in all_items
                if q in i.name.lower() or q in i.description.lower()
            ]

        return json.dumps({
            "status": "ok",
            "count": len(results),
            "indicators": [
                {
                    "id": i.id,
                    "name": i.name,
                    "description": i.description[:200],
                    "param_count": i.param_count,
                    "updated_at": i.updated_at,
                }
                for i in results
            ],
        })

    def _create(self, code: str, name: str) -> str:
        if not code:
            return json.dumps({"status": "error", "error": "code is required for create"})

        # Validate safety
        is_safe, err = validate_code_safety(code)
        if not is_safe:
            return json.dumps({"status": "error", "error": f"Safety check failed: {err}"})

        # Check quality
        hints = analyze_indicator_code_quality(code)
        fatals = [h for h in hints if h["severity"] == "error"]
        if fatals:
            return json.dumps({
                "status": "error",
                "error": "Code has fatal quality issues",
                "hints": fatals,
            })

        # Extract or provide name
        meta_name, _ = _extract_meta_from_code(code)
        if not meta_name and name:
            code = f'my_indicator_name = "{name}"\n' + code

        info = self._repo.save(code=code)
        params = IndicatorParamsParser.parse_params(code)
        strategy = StrategyConfigParser.parse(code)

        return json.dumps({
            "status": "ok",
            "action": "created",
            "indicator": {
                "id": info.id,
                "name": info.name,
                "description": info.description,
                "param_count": len(params),
                "strategy_config": strategy,
                "params": params,
            },
        })

    def _modify(self, indicator_id: str, code: str) -> str:
        if not indicator_id or not code:
            return json.dumps({"status": "error", "error": "indicator_id and code are required for modify"})

        existing = self._repo.get(indicator_id)
        if existing is None:
            return json.dumps({"status": "error", "error": f"Indicator not found: {indicator_id}"})

        is_safe, err = validate_code_safety(code)
        if not is_safe:
            return json.dumps({"status": "error", "error": f"Safety check failed: {err}"})

        info = self._repo.save(code=code, indicator_id=indicator_id)
        return json.dumps({
            "status": "ok",
            "action": "modified",
            "indicator": {
                "id": info.id,
                "name": info.name,
                "description": info.description,
                "param_count": info.param_count,
            },
        })

    def _verify(self, code_or_id: str) -> str:
        # Determine if this is an indicator ID or raw code
        existing = self._repo.get(code_or_id)
        if existing:
            code = self._repo.get_code(code_or_id) or ""
        else:
            code = code_or_id

        hints = analyze_indicator_code_quality(code)
        params = IndicatorParamsParser.parse_params(code)
        strategy = StrategyConfigParser.parse(code)

        error_count = sum(1 for h in hints if h["severity"] == "error")
        warn_count = sum(1 for h in hints if h["severity"] == "warn")
        info_count = sum(1 for h in hints if h["severity"] == "info")

        return json.dumps({
            "status": "ok",
            "valid": error_count == 0,
            "summary": f"{error_count} errors, {warn_count} warnings, {info_count} hints",
            "hints": hints,
            "params": params,
            "strategy_config": strategy,
        })

    def _promote(self, indicator_id: str, zoo_id: str) -> str:
        result = self._repo.promote_to_alpha(indicator_id=indicator_id, zoo_id=zoo_id)
        if result is None:
            return json.dumps({"status": "error", "error": f"Indicator not found: {indicator_id}"})
        return json.dumps({
            "status": "ok",
            "action": "promoted",
            "path": str(result),
            "zoo_id": zoo_id,
            "message": (
                f"Indicator {indicator_id} promoted to Alpha Zoo. "
                f"Review the generated file at {result} — you may need to "
                f"rewrite the compute() function for the wide-format panel."
            ),
        })

    def _delete(self, indicator_id: str) -> str:
        if self._repo.delete(indicator_id):
            return json.dumps({"status": "ok", "action": "deleted"})
        return json.dumps({"status": "error", "error": f"Indicator not found: {indicator_id}"})
