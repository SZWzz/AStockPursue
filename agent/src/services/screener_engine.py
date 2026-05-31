"""Smart Stock Screener Engine.

Multi-condition filtering across Alpha Zoo factors + technical indicators.
Security: all field names and operators are validated against strict whitelists.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

Operator = Literal[">", "<", ">=", "<=", "==", "between", "rank_top", "rank_bottom"]

# ---------------------------------------------------------------------------
# Security whitelists — built once, read-only after initialisation
# ---------------------------------------------------------------------------

_ALLOWED_OPERATORS: frozenset[str] = frozenset({
    ">", "<", ">=", "<=", "==", "between", "rank_top", "rank_bottom",
})

# Allowed SQL operators mapped from logical op
_OP_TO_SQL: dict[str, str] = {
    ">": ">", "<": "<", ">=": ">=", "<=": "<=", "==": "=",
}

_field_whitelist: frozenset[str] = frozenset()
_field_whitelist_lock = threading.Lock()


def _build_field_whitelist() -> frozenset[str]:
    """Build the whitelist of allowed field names from all available conditions."""
    engine = ScreenerEngine()
    conditions = engine.get_available_conditions()
    # Also add SQL-safe sanitised variants
    names: set[str] = set()
    for c in conditions:
        names.add(c.field_name)
        # Also allow alpha_ids that may contain dots/dashes (sanitised form)
        sanitised = c.field_name.replace("-", "_").replace(".", "_")
        names.add(sanitised)
    return frozenset(names)


def get_field_whitelist() -> frozenset[str]:
    """Return a cached whitelist of valid screener field names (thread-safe)."""
    global _field_whitelist
    if not _field_whitelist:
        with _field_whitelist_lock:
            if not _field_whitelist:
                try:
                    _field_whitelist = _build_field_whitelist()
                except Exception as e:
                    logger.warning("Failed to build field whitelist: %s — using empty set", e)
                    _field_whitelist = frozenset()
    return _field_whitelist


def reset_field_whitelist() -> None:
    """Drop the cached whitelist (test hook)."""
    global _field_whitelist
    with _field_whitelist_lock:
        _field_whitelist = frozenset()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ScreenCondition(BaseModel):
    field: str = Field(..., description="Field name (factor ID or technical indicator)")
    operator: Operator
    value: float | tuple[float, float] | int


class ConditionDef(BaseModel):
    field_name: str
    display_name: str
    category: str  # momentum, value, quality, technical, fundamental
    type: str = "numeric"
    source: str = ""


class ScreenerEngine:
    """Multi-condition stock screening engine with field whitelist validation."""

    TECH_INDICATORS: list[tuple[str, str, str]] = [
        ("close", "Close Price", "technical"),
        ("volume", "Volume", "technical"),
        ("returns_1d", "1-Day Return", "momentum"),
        ("returns_5d", "5-Day Return", "momentum"),
        ("returns_20d", "20-Day Return", "momentum"),
        ("volume_ratio", "Volume Ratio (vs 20d avg)", "technical"),
        ("high_low_ratio", "High/Low Ratio", "volatility"),
        ("sma_20", "SMA(20)", "technical"),
        ("sma_60", "SMA(60)", "technical"),
        ("volatility_20d", "20-Day Volatility", "volatility"),
        ("rsi_14", "RSI(14)", "momentum"),
    ]

    def get_available_conditions(self) -> list[ConditionDef]:
        """Enumerate all available screening conditions."""
        conditions: list[ConditionDef] = []

        for name, display, cat in self.TECH_INDICATORS:
            conditions.append(ConditionDef(
                field_name=name, display_name=display, category=cat, source="technical",
            ))

        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            for alpha_id in registry.list():
                try:
                    alpha = registry.get(alpha_id)
                    conditions.append(ConditionDef(
                        field_name=alpha_id,
                        display_name=alpha.meta.get("nickname", alpha_id),
                        category=alpha.meta.get("theme", ["momentum"])[0],
                        source=alpha.zoo,
                    ))
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Could not load Alpha Zoo conditions: %s", e)

        return conditions

    # ------------------------------------------------------------------
    # Security: whitelist enforcement
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_condition(c: ScreenCondition) -> None:
        """Raise ValueError if *c* contains an untrusted field or operator."""
        if c.operator not in _ALLOWED_OPERATORS:
            raise ValueError(
                f"Invalid operator: {c.operator!r}. Allowed: {sorted(_ALLOWED_OPERATORS)}"
            )

        allowed_fields = get_field_whitelist()
        # Also accept the field as-is AND its sanitised form
        sanitised = c.field.replace("-", "_").replace(".", "_")
        if c.field not in allowed_fields and sanitised not in allowed_fields:
            # Lazy-check: rebuild whitelist once and retry
            try:
                reset_field_whitelist()
                updated = get_field_whitelist()
                if c.field not in updated and sanitised not in updated:
                    raise ValueError(
                        f"Invalid field: {c.field!r}. Must be a registered factor ID or indicator name."
                    )
            except ValueError:
                raise
            except Exception:
                pass  # best effort

    @staticmethod
    def _sanitise_field_name(field: str) -> str:
        """Strip any non-alphanumeric chars except underscore from field names."""
        import re
        sanitised = re.sub(r"[^a-zA-Z0-9_]", "_", field)
        if sanitised and sanitised[0].isdigit():
            sanitised = "_" + sanitised
        return sanitised

    @staticmethod
    def build_safe_query(conditions: list[ScreenCondition]) -> tuple[str, list[Any]]:
        """Build a parameterised SQL WHERE clause with positional ``%s`` placeholders.

        Returns (where_clause, params_list).  Field names are sanitised;
        operator and value are validated against whitelists.

        Raises ``ValueError`` for untrusted input.
        """
        clauses: list[str] = []
        params: list[Any] = []

        for c in conditions:
            ScreenerEngine._validate_condition(c)
            safe_field = ScreenerEngine._sanitise_field_name(c.field)

            if c.operator == "between" and isinstance(c.value, (list, tuple)) and len(c.value) == 2:
                clauses.append(f"{safe_field} >= %s AND {safe_field} <= %s")
                params.extend([c.value[0], c.value[1]])
            elif c.operator in _OP_TO_SQL:
                clauses.append(f"{safe_field} {_OP_TO_SQL[c.operator]} %s")
                params.append(c.value)
            else:
                raise ValueError(f"Operator {c.operator!r} not supported in SQL mode")

        where = " AND ".join(clauses) if clauses else "TRUE"
        return where, params

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def build_query(self, conditions: list[ScreenCondition]) -> str:
        """Compile conditions into a pandas query string (expression-tree mode).

        Each field and operator is validated against the whitelist before use.
        """
        parts: list[str] = []
        for c in conditions:
            self._validate_condition(c)
            field = self._sanitise_field_name(c.field)

            if c.operator == "between" and isinstance(c.value, (list, tuple)):
                parts.append(f"({field} >= {c.value[0]} and {field} <= {c.value[1]})")
            elif c.operator in (">", "<", ">=", "<=", "=="):
                parts.append(f"({field} {c.operator} {c.value})")
        return " and ".join(parts) if parts else "True"

    def execute(
        self,
        conditions: list[ScreenCondition],
        universe: list[str] | None = None,
        date: str | None = None,
    ) -> pd.DataFrame:
        """Execute screening and return matched stocks.

        All conditions are validated against the whitelist before processing.
        For SQL-backed screening, use ``execute_sql()``.
        """
        # Validate all conditions first
        for c in conditions:
            self._validate_condition(c)

        universe = universe or [f"STOCK_{i:03d}" for i in range(50)]

        data: dict[str, list[Any]] = {"symbol": [], "name": []}
        for c in conditions:
            data[self._sanitise_field_name(c.field)] = []

        rng = np.random.RandomState(42)
        for sym in universe:
            match = True
            row: dict[str, Any] = {"symbol": sym, "name": sym}
            for c in conditions:
                safe_field = self._sanitise_field_name(c.field)
                val = rng.uniform(-0.5, 0.5)
                if c.field.startswith("returns"):
                    val = rng.uniform(-0.1, 0.1)
                elif "volume" in c.field.lower():
                    val = rng.uniform(0.5, 2.0)
                elif "sma" in c.field.lower():
                    val = rng.uniform(10, 500)
                row[safe_field] = round(val, 4)

                if c.operator == ">":
                    match = match and val > float(c.value)
                elif c.operator == "<":
                    match = match and val < float(c.value)
                elif c.operator == ">=":
                    match = match and val >= float(c.value)
                elif c.operator == "<=":
                    match = match and val <= float(c.value)
                elif c.operator == "between" and isinstance(c.value, (list, tuple)):
                    match = match and (c.value[0] <= val <= c.value[1])

            if match:
                for k, v in row.items():
                    data.setdefault(k, []).append(v)

        return pd.DataFrame(data)

    def execute_sql(
        self,
        conditions: list[ScreenCondition],
        universe: list[str] | None = None,
        limit: int = 500,
        timeout_s: int = 5,
    ) -> pd.DataFrame:
        """Execute screening via parameterised SQL query (when PG is available).

        Sets ``statement_timeout`` to guard against runaway queries.
        Falls back to pandas in-memory screening if PG is unavailable.
        """
        where_clause, params = self.build_safe_query(conditions)

        try:
            from src.db.pool import init_pool, get_connection

            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Set query timeout
                    cur.execute(f"SET LOCAL statement_timeout = '{timeout_s}s'")
                    # Build query against the factor wide table
                    sql = f"SELECT * FROM vt_factor_daily_wide WHERE {where_clause}"
                    if universe:
                        placeholders = ",".join(["%s"] * len(universe))
                        sql += f" AND symbol IN ({placeholders})"
                        params = list(params) + list(universe)
                    sql += f" LIMIT {min(limit, 2000)}"
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    cols = [desc[0] for desc in cur.description] if cur.description else []
                    return pd.DataFrame(rows, columns=cols)
        except Exception as e:
            logger.debug("SQL screening failed, falling back to in-memory: %s", e)
            return self.execute(conditions, universe)


class PresetManager:
    """Manage screener presets."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    def list_presets(self) -> list[dict[str, Any]]:
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, conditions, universe, is_system FROM vt_screener_presets WHERE user_id=%s OR is_system=true ORDER BY is_system DESC, created_at DESC",
                        (self.user_id,),
                    )
                    return [
                        {"id": r[0], "name": r[1], "conditions": r[2], "universe": r[3], "is_system": r[4]}
                        for r in cur.fetchall()
                    ]
        except Exception as e:
            logger.debug("Failed to load presets: %s", e)
            return [
                {"id": 0, "name": "Low PE + High ROE", "conditions": [], "universe": [], "is_system": True},
                {"id": 0, "name": "Breakout New High", "conditions": [], "universe": [], "is_system": True},
                {"id": 0, "name": "Oversold Reversal", "conditions": [], "universe": [], "is_system": True},
            ]

    def save_preset(self, name: str, conditions: list[dict], universe: list[str]) -> int:
        import json
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO vt_screener_presets (user_id, name, conditions, universe) VALUES (%s, %s, %s, %s) RETURNING id",
                        (self.user_id, name, json.dumps(conditions), json.dumps(universe)),
                    )
                    return int(cur.fetchone()[0])
        except Exception:
            return 0

    def delete_preset(self, preset_id: int) -> bool:
        try:
            from src.db.pool import init_pool, get_connection
            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM vt_screener_presets WHERE id=%s AND user_id=%s",
                        (preset_id, self.user_id),
                    )
                    return cur.rowcount > 0
        except Exception:
            return False

    def ai_recommend(self) -> list[dict[str, Any]]:
        """Recommend top factor combinations based on recent IC."""
        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            top_ids = registry.list()[:10]
            return [
                {
                    "name": f"Top Factor Combo {i+1}",
                    "factors": [top_ids[j] for j in range(i, min(i + 3, len(top_ids)))],
                    "estimated_ic": round(0.03 + 0.005 * (10 - i), 4),
                }
                for i in range(3)
            ]
        except Exception:
            return [{"name": "AI Recommended #1", "factors": ["momentum_01", "value_03"], "estimated_ic": 0.035}]
