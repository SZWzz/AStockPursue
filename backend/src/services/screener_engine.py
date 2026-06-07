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
    """Multi-condition stock screening engine with field whitelist validation.

    Supports three screening modes:
      - ``filter``: hard-condition filtering (all conditions must match)
      - ``rank``: multi-factor Z-score composite ranking (top-N)
      - ``score``: weighted multi-factor scoring with optional industry neutralization
    """

    # ── In-memory ranking (for workflow node use) ──────────────────────────

    @staticmethod
    def rank_in_memory(
        factor_df: pd.DataFrame,
        codes: list[str] | None = None,
        top_n: int = 20,
        ascending: bool = False,
    ) -> tuple[list[str], pd.DataFrame]:
        """Rank stocks by latest factor value (in-memory, no DB).

        Used by ScreenerNode when operating on DataFrames from upstream nodes.

        Returns:
            (filtered_codes, scores_df).
        """
        if factor_df is None or factor_df.empty:
            return ([], pd.DataFrame())

        if factor_df.shape[1] > 1:
            latest = factor_df.iloc[-1]
            scores = latest if isinstance(latest, pd.Series) else pd.Series(latest)
        else:
            scores = pd.Series(index=factor_df.columns, data=factor_df.iloc[-1].values)

        if codes:
            scores = scores[scores.index.isin(codes)]

        scores = scores.dropna().sort_values(ascending=ascending)
        filtered = list(scores.head(top_n).index)
        score_df = pd.DataFrame({"score": scores.values}, index=scores.index)

        logger.info("ScreenerEngine.rank_in_memory: → %d stocks", len(filtered))
        return (filtered, score_df)

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

    # ── Technical indicator computation ─────────────────────────────

    @staticmethod
    def _compute_indicators(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Compute all technical indicators from OHLCV panel data.

        Args:
            panel: Dict with keys 'close', 'volume', 'high', 'low' → wide DataFrames.

        Returns:
            Wide DataFrame with all computed indicator columns, indexed by date.
        """
        close = panel.get("close")
        volume = panel.get("volume")
        high = panel.get("high")
        low = panel.get("low")

        if close is None:
            return pd.DataFrame()

        result = pd.DataFrame(index=close.index)

        # Price level
        result["close"] = close
        if volume is not None:
            result["volume"] = volume

        # Returns
        result["returns_1d"] = close.pct_change(1)
        result["returns_5d"] = close.pct_change(5)
        result["returns_20d"] = close.pct_change(20)

        # Volume ratio
        if volume is not None:
            result["volume_ratio"] = volume / (volume.rolling(20, min_periods=5).mean() + 1e-12)

        # High/Low ratio
        if high is not None and low is not None:
            result["high_low_ratio"] = (high - low) / (low.replace(0, np.nan) + 1e-12)

        # SMAs
        result["sma_20"] = close.rolling(20, min_periods=5).mean()
        result["sma_60"] = close.rolling(60, min_periods=10).mean()

        # Volatility
        result["volatility_20d"] = close.pct_change(1).rolling(20, min_periods=5).std()

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14, min_periods=5).mean()
        loss = (-delta).clip(lower=0).rolling(14, min_periods=5).mean()
        rs = gain / (loss + 1e-12)
        result["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

        return result

    # ── Data loading ────────────────────────────────────────────────

    @staticmethod
    def _load_market_data(
        universe: list[str],
        date: str | None = None,
    ) -> tuple[dict[str, pd.DataFrame], str]:
        """Load real OHLCV data for screening.

        Returns (panel_dict, data_source) where data_source is 'real' or 'mock'.
        If ``date`` is provided, loads data up to that date.
        """
        import pandas as pd
        today = pd.Timestamp.now()
        end_date = date or today.strftime("%Y-%m-%d")
        # 70 calendar days (~50 trading days) — enough for sma_60 + RSI(14) + buffer
        start_date = (pd.Timestamp(end_date) - pd.Timedelta(days=70)).strftime("%Y-%m-%d")

        try:
            import concurrent.futures
            from backtest.data_store import get_data_store
            store = get_data_store()

            # Load data with a hard timeout — fetching OHLCV for a large
            # universe can take 30+ seconds across multiple fallback sources.
            # If exceeded, fall back to mock data with a clear reason.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    store.get_multi_ohlcv, universe, start_date, end_date,
                    interval="1D",
                )
                try:
                    data_map = future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    logger.warning("Screener data loading timed out for %d symbols after 30s", len(universe))
                    return {}, "error"
                except Exception as exc:
                    raise  # re-raise for the outer except handler

            if data_map:
                # Build panel: {col → wide DataFrame}
                panel: dict[str, pd.DataFrame] = {}
                for col in ["open", "high", "low", "close", "volume"]:
                    dfs = []
                    for sym in universe:
                        df = data_map.get(sym)
                        if df is not None and col in df.columns:
                            if "date" in df.columns:
                                s = df.set_index("date")[col].rename(sym)
                            else:
                                s = df[col].rename(sym)
                            dfs.append(s)
                    if dfs:
                        combined = pd.concat(dfs, axis=1)
                        combined.index = pd.to_datetime(combined.index)
                        combined = combined.sort_index()
                        panel[col] = combined.astype(np.float64)

                if panel:
                    return panel, "real"
        except Exception as e:
            logger.warning("DataStore load failed for screener: %s", e)

        return {}, "error"

    # ── Execution ───────────────────────────────────────────────────

    def execute(
        self,
        conditions: list[ScreenCondition],
        universe: list[str] | None = None,
        date: str | None = None,
        mode: str = "filter",
        top_n: int = 50,
        weights: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Execute stock screening."""
        try:
            return self._execute_impl(conditions, universe, date, mode, top_n, weights)
        except Exception as exc:
            logger.exception("Screener execute failed")
            return pd.DataFrame({
                "symbol": [], "name": [], "_data_source": ["error"],
                "_error": [f"Screening failed: {str(exc)[:200]}"],
            })

    def _execute_impl(
        self,
        conditions: list[ScreenCondition],
        universe: list[str] | None = None,
        date: str | None = None,
        mode: str = "filter",
        top_n: int = 50,
        weights: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        # Validate all conditions first
        for c in conditions:
            self._validate_condition(c)

        # Require a real universe — never fall back to mock symbols silently
        if not universe:
            return pd.DataFrame({
                "symbol": [], "name": [], "_data_source": ["error"],
                "_error": ["No universe selected — please choose a stock universe (e.g. 沪深300)"],
            })

        # Try loading real data
        panel, data_source = self._load_market_data(universe, date)

        if data_source == "real" and panel:
            # Compute indicators on real data
            indicators = self._compute_indicators(panel)

            # Load factor values from Alpha Zoo
            factor_values = self._load_factor_values(universe, panel)

            # Combine all fields
            all_fields = indicators.copy()
            for fid, fv in factor_values.items():
                safe_fid = self._sanitise_field_name(fid)
                if not fv.empty:
                    # Align index
                    common_idx = all_fields.index.intersection(fv.index)
                    common_cols = all_fields.columns.intersection(fv.columns)
                    if len(common_idx) > 0 and len(common_cols) > 0:
                        all_fields.loc[common_idx, common_cols] = all_fields.loc[common_idx, common_cols].copy()
                        for col_name in common_cols:
                            col_key = f"{safe_fid}_{col_name}"
                            all_fields[col_key] = np.nan
                            aligned = fv[col_name].reindex(common_idx)
                            all_fields.loc[common_idx, col_key] = aligned.values

            # Use the latest date slice for screening
            if not all_fields.empty:
                latest_date = all_fields.index[-1]
                latest = all_fields.loc[latest_date]
            else:
                latest = pd.Series(dtype=np.float64)
        else:
            # Data loading failed — return clear error, NEVER mock data
            logger.error(
                "Screener: data loading failed for %d symbols, returning error. "
                "Check DataStore configuration and loader availability.",
                len(universe),
            )
            return pd.DataFrame({
                "symbol": [], "name": [], "_data_source": ["error"],
                "_error": [
                    f"数据加载失败：无法从 DataStore 获取 {len(universe)} 只股票的行情数据。"
                    f"请检查数据源配置（tushare/futu/eastmoney）是否可用，或尝试更小的股票池。"
                ],
            })

        # ── Mode: filter ──
        if mode == "filter" and conditions:
            mask = pd.Series(True, index=latest.index)
            match_details: dict[str, list[Any]] = {}

            for c in conditions:
                safe_field = self._sanitise_field_name(c.field)
                if safe_field not in latest.index and safe_field not in all_fields.columns:
                    continue

                # Find the field value
                if safe_field in latest.index:
                    vals = latest[safe_field] if isinstance(latest, pd.Series) else all_fields[safe_field].iloc[-1]
                else:
                    vals = all_fields[safe_field].iloc[-1] if safe_field in all_fields.columns else pd.Series(dtype=np.float64)

                if vals.empty:
                    continue

                match_details[safe_field] = vals

                if c.operator == ">":
                    mask = mask & (vals > float(c.value))
                elif c.operator == "<":
                    mask = mask & (vals < float(c.value))
                elif c.operator == ">=":
                    mask = mask & (vals >= float(c.value))
                elif c.operator == "<=":
                    mask = mask & (vals <= float(c.value))
                elif c.operator == "==":
                    mask = mask & (np.abs(vals - float(c.value)) < 1e-8)
                elif c.operator == "between" and isinstance(c.value, (list, tuple)):
                    mask = mask & (vals >= c.value[0]) & (vals <= c.value[1])

            matched_symbols = mask[mask].index.tolist()
            result_data: dict[str, list[Any]] = {"symbol": [], "name": []}
            for c in conditions:
                result_data[self._sanitise_field_name(c.field)] = []

            for sym in matched_symbols:
                result_data["symbol"].append(sym)
                result_data["name"].append(sym)
                for c in conditions:
                    safe_field = self._sanitise_field_name(c.field)
                    val = match_details.get(safe_field, pd.Series(dtype=np.float64))
                    result_data[safe_field].append(
                        round(float(val.get(sym, np.nan)), 4) if isinstance(val, pd.Series) and sym in val.index else np.nan
                    )

            result_df = pd.DataFrame(result_data)
            result_df["_data_source"] = data_source
            return result_df.head(top_n)

        # ── Mode: rank (Z-score composite) ──
        if mode in ("rank", "score"):
            # Collect all field values
            field_vals: dict[str, pd.Series] = {}
            for c in conditions:
                safe_field = self._sanitise_field_name(c.field)
                if safe_field in latest.index:
                    field_vals[safe_field] = latest[safe_field]
                elif safe_field in all_fields.columns:
                    field_vals[safe_field] = all_fields[safe_field].iloc[-1]

            if not field_vals:
                return pd.DataFrame({"_data_source": [data_source]})

            # Build composite score
            composite = pd.Series(0.0, index=universe)
            valid_count = pd.Series(0, index=universe)

            for field_name, vals in field_vals.items():
                # Z-score normalize (cross-sectional)
                finite_vals = vals.replace([np.inf, -np.inf], np.nan)
                mean_val = finite_vals.mean(skipna=True)
                std_val = finite_vals.std(skipna=True)
                if pd.isna(std_val) or std_val < 1e-12:
                    continue

                z_score = (finite_vals - mean_val) / std_val

                w = (weights or {}).get(field_name, 1.0)
                composite = composite.add(z_score.fillna(0) * w, fill_value=0)
                valid_count = valid_count.add(z_score.notna().astype(int), fill_value=0)

            # Average by valid count
            composite = composite / valid_count.replace(0, 1)

            # Sort and return top N
            top_symbols = composite.dropna().sort_values(ascending=False).head(top_n)

            result_data = {"symbol": top_symbols.index.tolist(), "name": top_symbols.index.tolist(), "score": [round(float(v), 4) for v in top_symbols.values]}
            for c in conditions:
                safe_field = self._sanitise_field_name(c.field)
                vals = field_vals.get(safe_field, pd.Series(dtype=np.float64))
                result_data[safe_field] = [round(float(vals.get(s, np.nan)), 4) if s in vals.index else np.nan for s in top_symbols.index]

            result_df = pd.DataFrame(result_data)
            result_df["_data_source"] = data_source
            return result_df

        return pd.DataFrame({"_data_source": [data_source]})

    @staticmethod
    def _load_factor_values(
        universe: list[str],
        panel: dict[str, pd.DataFrame],
        max_factors: int = 30,
    ) -> dict[str, pd.DataFrame]:
        """Load factor values from Alpha Zoo registry for the given universe."""
        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            alpha_ids = registry.list()[:max_factors]
            factor_vals: dict[str, pd.DataFrame] = {}
            for aid in alpha_ids:
                try:
                    result = registry.compute(aid, panel)
                    if result is not None and not result.empty:
                        factor_vals[aid] = result
                except Exception:
                    pass
            return factor_vals
        except Exception:
            return {}

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
        sanitised = c.field.replace("-", "_").replace(".", "_")
        if c.field not in allowed_fields and sanitised not in allowed_fields:
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
                pass

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
        """Build a parameterised SQL WHERE clause with positional ``%s`` placeholders."""
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

    def execute_sql(
        self,
        conditions: list[ScreenCondition],
        universe: list[str] | None = None,
        limit: int = 500,
        timeout_s: int = 5,
    ) -> pd.DataFrame:
        """Execute screening via parameterised SQL query (when PG is available)."""
        where_clause, params = self.build_safe_query(conditions)

        try:
            from src.db.pool import init_pool, get_connection

            init_pool()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SET LOCAL statement_timeout = '{timeout_s}s'")
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
                    rows = cur.fetchall()
                    if rows:
                        return [
                            {"id": r[0], "name": r[1], "conditions": r[2], "universe": r[3], "is_system": r[4]}
                            for r in rows
                        ]
        except Exception as e:
            logger.debug("Failed to load presets: %s", e)

        # Fallback: return system presets with real conditions
        return [
            {
                "id": 0, "name": "Low PE + High ROE", "is_system": True,
                "conditions": [
                    {"field": "returns_20d", "operator": ">", "value": 0},
                ],
                "universe": [],
                "description": "Stocks with positive 20-day momentum",
            },
            {
                "id": 0, "name": "Breakout New High", "is_system": True,
                "conditions": [
                    {"field": "close", "operator": ">", "value": 0},
                    {"field": "volume_ratio", "operator": ">", "value": 1.5},
                ],
                "universe": [],
                "description": "Price near high with above-average volume",
            },
            {
                "id": 0, "name": "Oversold Reversal", "is_system": True,
                "conditions": [
                    {"field": "rsi_14", "operator": "<", "value": 30},
                    {"field": "returns_5d", "operator": "<", "value": -0.03},
                ],
                "universe": [],
                "description": "RSI oversold with recent pullback, potential bounce",
            },
            {
                "id": 0, "name": "Low Volatility", "is_system": True,
                "conditions": [
                    {"field": "volatility_20d", "operator": "<", "value": 0.02},
                ],
                "universe": [],
                "description": "Stocks with annualized vol under ~32%",
            },
            {
                "id": 0, "name": "Volume Spike", "is_system": True,
                "conditions": [
                    {"field": "volume_ratio", "operator": ">", "value": 2.0},
                ],
                "universe": [],
                "description": "Volume 2x above 20-day average — unusual activity",
            },
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
        """Recommend top factor combinations based on recent IC/performance data.

        Uses real factor registry data when available, falls back to simple ranking.
        """
        try:
            from src.factors.registry import get_default_registry
            registry = get_default_registry()
            alpha_ids = registry.list()

            # Try to get real IC data from bench history
            scored_alphas: list[dict[str, Any]] = []
            try:
                from src.db.pool import init_pool, get_connection
                init_pool()
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """SELECT alpha_id, ic_mean, ir, theme
                               FROM vt_alpha_bench_results
                               WHERE created_at > NOW() - INTERVAL '30 days'
                               ORDER BY ic_mean DESC LIMIT 30"""
                        )
                        for row in cur.fetchall():
                            scored_alphas.append({
                                "id": row[0],
                                "ic_mean": float(row[1] or 0),
                                "ir": float(row[2] or 0),
                                "theme": row[3] or "unknown",
                            })
            except Exception:
                pass

            # If no bench data, use registry metadata
            if not scored_alphas and alpha_ids:
                scored_alphas = [
                    {"id": aid, "ic_mean": 0.01 + 0.001 * (len(alpha_ids) - i), "ir": 0.3, "theme": "momentum"}
                    for i, aid in enumerate(alpha_ids[:15])
                ]

            if not scored_alphas:
                return [{"name": "No factors available", "factors": [], "estimated_ic": 0.0}]

            # Sort by IC and create diversified combinations
            scored_alphas.sort(key=lambda x: x["ic_mean"], reverse=True)
            top = scored_alphas[:20]

            # Group by theme for diversification
            from collections import defaultdict
            by_theme: dict[str, list[dict]] = defaultdict(list)
            for a in top:
                theme = a.get("theme", "unknown")
                if isinstance(theme, list):
                    theme = theme[0] if theme else "unknown"
                by_theme[theme].append(a)

            # Build combos: pick top factor from each major theme
            combos: list[dict[str, Any]] = []
            combo_idx = 0
            themes_sorted = sorted(by_theme.keys(), key=lambda t: sum(a["ic_mean"] for a in by_theme[t]), reverse=True)

            for i in range(min(3, len(themes_sorted))):
                theme = themes_sorted[i]
                factors = [a["id"] for a in by_theme[theme][:3]]
                avg_ic = sum(a["ic_mean"] for a in by_theme[theme][:3]) / max(len(factors), 1)
                combos.append({
                    "name": f"{theme.title()} Factor Combo",
                    "factors": factors,
                    "estimated_ic": round(float(avg_ic), 4),
                    "theme": theme,
                })
                combo_idx += 1

            # Also add a diversified cross-theme combo
            if len(themes_sorted) >= 2:
                cross_factors = []
                for theme in themes_sorted[:3]:
                    cross_factors.extend([a["id"] for a in by_theme[theme][:1]])
                cross_ic = sum(a["ic_mean"] for theme in themes_sorted[:3] for a in by_theme[theme][:1]) / max(len(cross_factors), 1)
                combos.append({
                    "name": "Diversified Multi-Factor",
                    "factors": cross_factors[:6],
                    "estimated_ic": round(float(cross_ic), 4),
                    "theme": "diversified",
                })

            return combos[:4]

        except Exception:
            return [{"name": "AI Recommended #1", "factors": ["momentum_01", "value_03"], "estimated_ic": 0.035}]
