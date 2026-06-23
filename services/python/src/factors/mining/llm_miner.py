"""LLM-guided factor discovery.

Extracts alpha factor formulas from research papers (PDF),
cross-market factor transfer, and multi-LLM debate filtering.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.factors.mining.sandbox_pandas import SandboxError, SandboxNumpy, SandboxPandas

logger = logging.getLogger(__name__)


class FactorCandidate(BaseModel):
    """A candidate factor discovered by LLM."""

    name: str = Field(default="", description="Short name for the factor")
    formula: str = Field(..., description="Python/pandas formula string")
    description: str = Field(default="", description="Natural language description")
    source: str = Field(default="llm", description="Source: pdf, transfer, debate")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    expression_json: dict[str, Any] | None = None


EXTRACTION_PROMPT = """You are a quantitative finance researcher. Extract alpha factor formulas from the following research text.

For each factor found, output a JSON object with:
- name: short descriptive name (snake_case)
- formula: the mathematical formula expressed as pandas operations using these local variables:
  'close', 'open_', 'high', 'low', 'volume' — wide DataFrames (index=dates, columns=symbols)
- description: one-line explanation of what this factor measures and why it works economically

Available operations on DataFrames:
- .pct_change(N) for returns over N periods
- .rolling(N).mean() / .std() / .max() / .min() for rolling windows
- .shift(N) for lag (use positive N only — negative shift is lookahead bias!)
- .rank(axis=1, pct=True) for cross-sectional percentile rank
- .diff(N) for difference over N periods
- Arithmetic: + - * / work element-wise
- .corr(other) for correlation, .rolling(N).corr(other) for rolling correlation
- .abs(), np.log(x.clip(lower=1e-12)), np.sqrt(x.clip(lower=0)), np.sign(x)

IMPORTANT RULES:
1. NEVER use .shift(-N) or .pct_change(-N) — that's lookahead bias (future data)
2. All rolling windows should use at least 5 min_periods
3. Use .replace([np.inf, -np.inf], np.nan) after division
4. Cross-sectional operations use axis=1 (across stocks)

HIGH-QUALITY FACTOR EXAMPLES (few-shot):

Example 1 — Momentum:
  name: momentum_20d
  formula: (close - close.shift(20)) / close.shift(20).replace(0, np.nan)
  description: 20-day price momentum — stocks that have risen tend to continue rising in the short term

Example 2 — Volume Abnormal:
  name: volume_ratio_abnormal
  formula: volume / volume.rolling(60, min_periods=10).mean()
  description: Abnormal volume relative to 60-day average — high volume often precedes large moves

Example 3 — Reversal:
  name: short_term_reversal_5d
  formula: -close.pct_change(5).rank(axis=1, pct=True)
  description: 5-day short-term reversal — stocks that fell sharply tend to bounce

Example 4 — Volatility:
  name: volatility_20d
  formula: close.pct_change(1).rolling(20, min_periods=5).std()
  description: 20-day realized volatility — low-vol stocks tend to have better risk-adjusted returns

Example 5 — Range:
  name: intraday_range
  formula: (high - low) / close
  description: Normalized intraday price range — wide ranges indicate uncertainty or reversal risk

Market context: {market_context}

Text to analyze:
{text}

Output as a JSON array of factor objects. Only output valid JSON, no commentary."""

REFINE_PROMPT = """You are a quantitative finance researcher. A factor formula you created was tested against real market data and the results were suboptimal.

ORIGINAL FORMULA:
  Name: {name}
  Formula: {formula}
  Description: {description}

EVALUATION RESULTS:
  Train IC: {train_ic} (target: >0.02)
  Coverage: {coverage} (target: >0.5)
  Max Zoo Correlation: {max_zoo_corr} (target: <0.7)
  Issues: {issues}

Please REFINE this factor to improve its performance. Consider:
1. Adjusting lookback windows (try different values: 5, 10, 20, 40, 60)
2. Adding cross-sectional normalization (.rank(axis=1, pct=True))
3. Removing noisy components that reduce coverage
4. Adding complementary signals (volume, volatility filters)
5. Using different transformations (log, sqrt, z-score)

Output the refined factor as JSON:
- name: refined name (append _v2, _v3 etc.)
- formula: the improved formula
- description: what changed and why
- change_log: brief explanation of modifications made

Only output valid JSON, no commentary."""

EXPLAIN_PROMPT = """You are a quantitative finance researcher. Explain this alpha factor in detail.

Factor: {name}
Formula: {formula}
IC: {train_ic}
Sharpe: {train_sharpe}

Please provide a comprehensive explanation covering:
1. Economic intuition: What market anomaly or behavior does this factor capture?
2. Mathematical interpretation: Walk through the formula step by step in plain language
3. Market regime suitability: Bull/Bear/Sideways — when does this factor work best?
4. Risk considerations: What could cause this factor to stop working?
5. Suggested usage: Recommended rebalance frequency, position sizing, stop-loss logic

Output as JSON:
- intuition: string
- math_explanation: string
- market_regime: string
- risks: string
- usage: string

Only output valid JSON, no commentary."""

DEBATE_PROMPT = """You are a {role} reviewing alpha factor candidates for a quantitative trading system.

These are candidate factors discovered by genetic programming / LLM:

{candidates}

As a {role}, evaluate each factor for:
1. Financial/economic logic: Does this factor make sense economically?
2. Robustness: Is it likely to overfit? Are there lookahead concerns?
3. Redundancy: Does it duplicate known factors?
4. Practicality: Can it be traded with reasonable costs?

For each factor, give a score (0-100) and a brief verdict.

Output JSON:
[{{"factor_index": 0, "score": 75, "verdict": "brief reason", "pass": true}}]

Only output valid JSON, no commentary."""


# ---------------------------------------------------------------------------
# Cost & rate-limit state (module-level)
# ---------------------------------------------------------------------------

_cost_lock = threading.Lock()
_daily_token_usage: dict[str, int] = {}  # date_str -> tokens used
_daily_call_count: dict[str, int] = {}   # date_str -> call count
_max_daily_tokens: int = int(os.environ.get("FM_LLM_MAX_DAILY_TOKENS", "500000"))  # default 500k
_max_calls_per_minute: int = int(os.environ.get("FM_LLM_MAX_CALLS_PER_MINUTE", "10"))
_call_timestamps: list[float] = []  # rolling window of recent call times (seconds)
_call_lock = threading.Lock()

_JSON_SCHEMA_FACTORS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short descriptive name (snake_case)"},
            "formula": {"type": "string", "description": "Python/pandas formula using panel DataFrame"},
            "description": {"type": "string", "description": "One-line economic rationale"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["name", "formula", "description"],
    },
}

_JSON_SCHEMA_DEBATE = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "factor_index": {"type": "integer"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "verdict": {"type": "string"},
            "pass": {"type": "boolean"},
        },
        "required": ["factor_index", "score", "verdict", "pass"],
    },
}

_JSON_SCHEMA_REVIEW = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "index": {"type": "integer"},
            "pass": {"type": "boolean"},
            "reason": {"type": "string"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["index", "pass", "reason", "score"],
    },
}


def _check_rate_limit() -> None:
    """Raise RuntimeError if LLM call rate limit exceeded."""
    now = time.monotonic()
    with _call_lock:
        # Clean timestamps older than 60s
        cutoff = now - 60.0
        global _call_timestamps
        _call_timestamps = [t for t in _call_timestamps if t > cutoff]
        if len(_call_timestamps) >= _max_calls_per_minute:
            raise RuntimeError(
                f"LLM rate limit exceeded ({_max_calls_per_minute} calls/min). "
                "Try again later or increase FM_LLM_MAX_CALLS_PER_MINUTE."
            )
        _call_timestamps.append(now)


def _check_token_budget(estimated_tokens: int = 2000) -> None:
    """Raise RuntimeError if daily token budget would be exceeded."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _cost_lock:
        used = _daily_token_usage.get(today, 0)
        if used + estimated_tokens > _max_daily_tokens:
            raise RuntimeError(
                f"Daily LLM token budget exceeded ({used}/{_max_daily_tokens}). "
                "Budget resets at midnight UTC. Increase FM_LLM_MAX_DAILY_TOKENS if needed."
            )


def _record_usage(tokens: int) -> None:
    """Record LLM token usage for the current day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _cost_lock:
        _daily_token_usage[today] = _daily_token_usage.get(today, 0) + tokens
        _daily_call_count[today] = _daily_call_count.get(today, 0) + 1


def get_llm_usage_stats() -> dict[str, Any]:
    """Return current-day LLM usage stats for monitoring."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _cost_lock:
        return {
            "date": today,
            "tokens_used": _daily_token_usage.get(today, 0),
            "calls": _daily_call_count.get(today, 0),
            "token_budget": _max_daily_tokens,
            "budget_remaining": _max_daily_tokens - _daily_token_usage.get(today, 0),
        }


class LLMFactorMiner:
    """LLM-guided factor discovery engine with JSON Schema enforcement and cost controls."""

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._provider = llm_provider

    def _call_llm(
        self,
        prompt: str,
        system: str = "You are a quantitative finance researcher.",
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Call the LLM provider with optional JSON Schema structured output.

        Rate limit and token budget checks are enforced on every call.
        """
        # Cost & rate controls
        try:
            _check_rate_limit()
            _check_token_budget()
        except RuntimeError as e:
            logger.warning("LLM call blocked: %s", e)
            return ""

        if self._provider is not None:
            try:
                result = self._provider(prompt, system=system)
                _record_usage(2000)  # rough estimate
                return result
            except Exception as e:
                logger.warning("Custom LLM provider failed: %s", e)
                return ""

        # Try LangChain with JSON Schema support when available
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from src.agent.llm import _get_chat_model

            model = _get_chat_model()
            if model is None:
                logger.warning("No LLM model configured")
                return ""

            messages: list = [SystemMessage(content=system), HumanMessage(content=prompt)]

            # Request structured output if JSON Schema provided and model supports it
            extra_kwargs: dict[str, Any] = {}
            if json_schema is not None:
                # Some LLM providers (OpenAI, etc.) support response_format
                extra_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "factors",
                        "schema": json_schema,
                    },
                }

            result = model.invoke(messages, **extra_kwargs)
            content = str(result.content) if result else ""

            # Estimate tokens from response + prompt length
            estimated_tokens = len(prompt) // 3 + len(content) // 3
            _record_usage(max(estimated_tokens, 100))

            return content
        except Exception as e:
            logger.debug("LLM call failed (langchain): %s", e)
            # Fallback: try without json_schema
            if json_schema is not None:
                try:
                    self._call_llm(prompt, system=system, json_schema=None)
                except Exception:
                    pass
            return ""

    def _parse_json_response(self, text: str) -> list[dict[str, Any]]:
        """Extract JSON array from LLM response text."""
        # Try direct parse
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            return []
        except json.JSONDecodeError:
            pass

        # Try to extract JSON between markers
        for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
            match = re.search(pattern, text)
            if match:
                try:
                    data = json.loads(match.group())
                    if isinstance(data, list):
                        return data
                    return [data]
                except json.JSONDecodeError:
                    continue

        logger.warning("Could not parse LLM response as JSON: %s...", text[:200])
        return []

    # ── Market context ─────────────────────────────────────────────

    @staticmethod
    def _get_market_context() -> str:
        """Build a brief market context string for factor extraction prompts.

        Describes current market conditions so the LLM can tailor factors
        to the prevailing regime.
        """
        try:
            from backtest.data_store import get_data_store
            store = get_data_store()
            # Try to get recent SPY data for US market context
            df = store.get_ohlcv("SPY.US", "2026-05-01", "2026-05-31", interval="1D")
            if df is not None and len(df) >= 10:
                close = df["close"]
                ret_1m = (close.iloc[-1] / close.iloc[0] - 1) * 100
                vol_20d = close.pct_change().rolling(20).std().iloc[-1] * 100
                regime = "bullish" if ret_1m > 2 else "bearish" if ret_1m < -2 else "sideways"
                v_level = "high" if vol_20d > 2 else "moderate" if vol_20d > 1 else "low"
                return (
                    f"Current market: {regime} (1M return: {ret_1m:.1f}%), "
                    f"volatility: {v_level} ({vol_20d:.1f}% daily). "
                    f"Prefer {'defensive/quality' if regime == 'bearish' else 'momentum/trend' if regime == 'bullish' else 'reversal/mean-reversion'} factors."
                )
        except Exception:
            pass
        return "Market context unavailable — design factors suitable for general market conditions."

    # ── Sandbox pre-execution ───────────────────────────────────────

    @staticmethod
    def _sandbox_pre_run(formula: str) -> tuple[bool, str, dict[str, Any] | None]:
        """Execute a formula on a tiny sandbox dataset to catch runtime errors.

        Returns (success, error_message, result_stats).
        """
        import numpy as np
        import pandas as pd

        try:
            # Create tiny test panel: 3 stocks × 30 days
            dates = pd.date_range("2024-01-01", periods=30, freq="B")
            symbols = ["S1", "S2", "S3"]
            rng = np.random.RandomState(42)
            close = pd.DataFrame(
                100 + rng.randn(30, 3).cumsum(axis=0),
                index=dates, columns=symbols, dtype=np.float64,
            )
            panel = {
                "close": close,
                "open_": close.shift(1).fillna(close) * (1 + rng.randn(30, 3) * 0.005),
                "high": close * (1 + np.abs(rng.randn(30, 3)) * 0.01),
                "low": close * (1 - np.abs(rng.randn(30, 3)) * 0.01),
                "volume": pd.DataFrame(np.abs(rng.randn(30, 3)) * 1e6, index=dates, columns=symbols),
            }

            safe_builtins = {
                "True": True, "False": False, "None": None,
                "abs": abs, "min": min, "max": max, "round": round, "len": len,
            }
            safe_locals = {
                "panel": panel, "close": close, "open_": panel["open_"],
                "high": panel["high"], "low": panel["low"], "volume": panel["volume"],
                "pd": SandboxPandas(), "np": SandboxNumpy(),
                "abs": abs, "min": min, "max": max,
                "round": round, "len": len,
            }

            result = eval(formula, {"__builtins__": safe_builtins}, safe_locals)
            if isinstance(result, pd.DataFrame) and not result.empty:
                arr = result.to_numpy(dtype=np.float64)
                return True, "", {
                    "shape": list(result.shape),
                    "nan_ratio": round(float(np.isnan(arr).sum()) / arr.size, 4),
                    "inf_count": int(np.isinf(arr).sum()),
                }
            return False, "Formula did not return a valid DataFrame", None
        except Exception as e:
            return False, str(e), None

    # ── Formula validation ──────────────────────────────────────────

    @staticmethod
    def _validate_formula_syntax(formula: str) -> tuple[bool, str]:
        """Validate that a formula string is syntactically valid Python/pandas.

        Returns (is_valid, error_message).
        """
        if not formula or not formula.strip():
            return False, "Empty formula"

        import ast
        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError as e:
            return False, f"Python syntax error: {e}"

        # Check for dangerous constructs
        dangerous = {"__import__", "exec", "eval", "compile", "open", "os.", "sys.", "subprocess", "shutil"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in dangerous:
                return False, f"Blocked dangerous name: {node.id}"
            if isinstance(node, ast.Attribute):
                full = ast.unparse(node) if hasattr(ast, "unparse") else str(node)
                if any(d in full for d in dangerous):
                    return False, f"Blocked dangerous call: {full}"
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in dangerous:
                    return False, f"Blocked dangerous function: {node.func.id}"

        # Check that the expression references allowed DataFrame operations
        allowed = {"panel", "pd", "np", "abs", "min", "max", "round", "len", "range"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in allowed and not node.id.startswith("_"):
                # Allow as part of method chains (e.g., panel['close'].pct_change(1))
                pass

        return True, ""

    def extract_from_text(self, text: str) -> list[FactorCandidate]:
        """Extract factor formulas from research text.

        Pipeline: LLM extraction → AST syntax check → sandbox pre-run → return valid candidates.

        Args:
            text: Research paper or article text content.

        Returns:
            List of FactorCandidate objects (syntax-valid AND runnable formulas).
        """
        market_ctx = self._get_market_context()
        prompt = EXTRACTION_PROMPT.format(market_context=market_ctx, text=text[:8000])
        response = self._call_llm(prompt, json_schema=_JSON_SCHEMA_FACTORS)
        if not response:
            return []

        raw_factors = self._parse_json_response(response)
        candidates: list[FactorCandidate] = []
        rejected_syntax = 0
        rejected_runtime = 0
        for rf in raw_factors:
            try:
                formula = rf.get("formula", "")

                # A3: Sandbox pre-execution — catch runtime errors before returning
                sandbox_ok, sandbox_err, sandbox_stats = self._sandbox_pre_run(formula)
                if not sandbox_ok:
                    logger.debug("Sandbox rejected formula: %s — %s", formula[:60], sandbox_err)
                    rejected_runtime += 1
                    continue

                # Syntax validation (double-check)
                is_valid, err_msg = self._validate_formula_syntax(formula)
                if not is_valid:
                    logger.debug("Rejected invalid formula: %s — %s", formula[:60], err_msg)
                    rejected_syntax += 1
                    continue

                confidence = rf.get("confidence", 0.5)
                # Adjust confidence based on sandbox stats
                if sandbox_stats:
                    nan_r = sandbox_stats.get("nan_ratio", 1)
                    if nan_r < 0.1:
                        confidence = min(1.0, confidence + 0.1)
                    elif nan_r > 0.5:
                        confidence = max(0.1, confidence - 0.2)

                candidates.append(FactorCandidate(
                    name=rf.get("name", "unknown"),
                    formula=formula,
                    description=rf.get("description", ""),
                    source="pdf",
                    confidence=confidence,
                    expression_json={"sandbox_stats": sandbox_stats} if sandbox_stats else None,
                ))
            except Exception as e:
                logger.debug("Failed to parse factor candidate: %s", e)

        total = len(candidates) + rejected_syntax + rejected_runtime
        if total > 0:
            logger.info("LLM extraction: %d accepted, %d syntax rejected, %d runtime rejected (total %d)",
                         len(candidates), rejected_syntax, rejected_runtime, total)

        return candidates

    def extract_from_pdf(self, pdf_path: str | Path) -> list[FactorCandidate]:
        """Extract factors from a PDF research paper.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of FactorCandidate objects.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error("PDF not found: %s", pdf_path)
            return []

        # Try to read PDF
        text = ""
        try:
            # Try PyPDF2 first
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(str(pdf_path))
                for page in reader.pages:
                    text += page.extract_text() or ""
            except ImportError:
                # Fallback: try pdfplumber
                try:
                    import pdfplumber
                    with pdfplumber.open(str(pdf_path)) as pdf:
                        for page in pdf.pages:
                            text += page.extract_text() or ""
                except ImportError:
                    logger.error("No PDF reader available (PyPDF2 or pdfplumber)")
                    return []
        except Exception as e:
            logger.error("Failed to read PDF %s: %s", pdf_path, e)
            return []

        if not text.strip():
            logger.warning("No text extracted from PDF: %s", pdf_path)
            return []

        return self.extract_from_text(text)

    def cross_market_transfer(
        self,
        source_market: str,
        target_market: str,
        factor_description: str,
    ) -> list[FactorCandidate]:
        """Adapt a factor from one market to another.

        Args:
            source_market: Source market (e.g., 'equity_us').
            target_market: Target market (e.g., 'equity_cn').
            factor_description: Description of the factor to transfer.

        Returns:
            List of adapted FactorCandidate objects.
        """
        prompt = f"""Adapt the following quantitative factor from {source_market} to {target_market}.

Original factor:
{factor_description}

For {target_market}, consider:
- Market microstructure differences (trading hours, T+1 vs T+0, short-sale constraints)
- Data availability differences
- Typical parameter adjustments (e.g., lookback windows)
- Sector/industry classification differences

Output adapted factors as JSON array with: name, formula, description.
Only output valid JSON."""
        response = self._call_llm(prompt)
        if not response:
            return []

        raw = self._parse_json_response(response)
        return [
            FactorCandidate(
                name=r.get("name", "transferred"),
                formula=r.get("formula", ""),
                description=r.get("description", ""),
                source="transfer",
                confidence=0.6,
            )
            for r in raw
        ]

    def debate_filter(
        self,
        candidates: list[FactorCandidate],
        n_rounds: int = 3,
    ) -> list[FactorCandidate]:
        """Multi-LLM debate to filter and score factor candidates.

        Three personas (quant researcher, risk manager, portfolio manager)
        independently review each candidate, then votes are aggregated.

        Args:
            candidates: Candidate factors to evaluate.
            n_rounds: Number of debate rounds.

        Returns:
            Filtered and re-scored candidates.
        """
        if not candidates:
            return []

        roles = ["quantitative researcher", "risk manager", "portfolio manager"]
        all_scores: dict[int, list[int]] = {i: [] for i in range(len(candidates))}

        candidates_text = "\n\n".join(
            f"Factor {i}: {c.name}\n  Formula: {c.formula}\n  Description: {c.description}"
            for i, c in enumerate(candidates)
        )

        for role in roles:
            prompt = DEBATE_PROMPT.format(role=role, candidates=candidates_text)
            response = self._call_llm(prompt, json_schema=_JSON_SCHEMA_DEBATE)
            if not response:
                continue

            results = self._parse_json_response(response)
            for r in results:
                idx = r.get("factor_index", -1)
                score = r.get("score", 50)
                if 0 <= idx < len(candidates):
                    all_scores[idx].append(score)

        # Average scores, filter low-scoring
        filtered: list[FactorCandidate] = []
        for i, c in enumerate(candidates):
            scores = all_scores.get(i, [])
            if not scores:
                filtered.append(c)
                continue
            avg_score = sum(scores) / len(scores)
            if avg_score >= 40:  # Keep if average score >= 40
                c.confidence = avg_score / 100.0
                c.source = "debate"
                filtered.append(c)

        return filtered

    def self_refine(
        self,
        name: str,
        formula: str,
        description: str,
        train_ic: float,
        coverage: float = 0.0,
        max_zoo_corr: float = 0.0,
        max_iterations: int = 3,
    ) -> list[FactorCandidate]:
        """A2: Self-Refinement loop — iteratively improve a weak factor.

        If a factor's IC is below threshold, sends it back to the LLM with
        evaluation feedback and asks for improvements.  Repeats up to
        ``max_iterations`` times until IC improves or budget exhausted.

        Args:
            name: Original factor name.
            formula: Original formula string.
            description: Original description.
            train_ic: IC from evaluation (e.g., from evaluate_factor tool).
            coverage: Data coverage ratio (0-1).
            max_zoo_corr: Max correlation with existing zoo factors.
            max_iterations: Max refinement rounds (controls token cost).

        Returns:
            List of refined FactorCandidate objects (one per iteration that
            passed validation).
        """
        refined: list[FactorCandidate] = []
        current_name = name
        current_formula = formula
        current_desc = description

        issues = []
        if abs(train_ic) < 0.02:
            issues.append("IC too low (below 0.02)")
        if coverage < 0.5:
            issues.append(f"Low coverage ({coverage:.1%})")
        if max_zoo_corr > 0.7:
            issues.append(f"Too correlated with existing factor (r={max_zoo_corr:.2f})")

        if not issues:
            return refined  # Factor is fine, no refinement needed

        for iteration in range(max_iterations):
            prompt = REFINE_PROMPT.format(
                name=current_name,
                formula=current_formula,
                description=current_desc,
                train_ic=f"{train_ic:.6f}",
                coverage=f"{coverage:.1%}",
                max_zoo_corr=f"{max_zoo_corr:.2f}",
                issues="; ".join(issues),
            )

            response = self._call_llm(prompt, json_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "formula": {"type": "string"},
                    "description": {"type": "string"},
                    "change_log": {"type": "string"},
                },
                "required": ["name", "formula", "description"],
            })

            if not response:
                break

            parsed = self._parse_json_response(response)
            if not parsed:
                break

            rf = parsed[0] if isinstance(parsed, list) else parsed
            new_formula = rf.get("formula", "")
            new_name = rf.get("name", f"{name}_v{iteration + 2}")
            new_desc = rf.get("description", current_desc)

            # Validate and sandbox the refined formula
            is_valid, err = self._validate_formula_syntax(new_formula)
            if not is_valid:
                logger.debug("Refined formula failed syntax check: %s", err)
                continue

            sandbox_ok, sandbox_err, sandbox_stats = self._sandbox_pre_run(new_formula)
            if not sandbox_ok:
                logger.debug("Refined formula failed sandbox: %s", sandbox_err)
                continue

            refined.append(FactorCandidate(
                name=new_name,
                formula=new_formula,
                description=f"{new_desc} [Refined v{iteration + 2}]",
                source="self_refine",
                confidence=0.6 + 0.1 * iteration,
                expression_json={
                    "original_name": name,
                    "refinement_round": iteration + 1,
                    "change_log": rf.get("change_log", ""),
                    "sandbox_stats": sandbox_stats,
                },
            ))

            # Update for next iteration
            current_name = new_name
            current_formula = new_formula
            current_desc = new_desc

        return refined

    def explain_factor(
        self,
        name: str,
        formula: str,
        train_ic: float = 0.0,
        train_sharpe: float = 0.0,
    ) -> dict[str, str]:
        """B3: Generate a comprehensive explanation of a factor.

        Explains economic intuition, math, market regime, risks, and usage.

        Args:
            name: Factor name.
            formula: Factor formula string.
            train_ic: IC from evaluation.
            train_sharpe: Sharpe from evaluation.

        Returns:
            Dict with intuition, math_explanation, market_regime, risks, usage keys.
        """
        prompt = EXPLAIN_PROMPT.format(
            name=name, formula=formula,
            train_ic=f"{train_ic:.4f}", train_sharpe=f"{train_sharpe:.2f}",
        )
        response = self._call_llm(prompt, json_schema={
            "type": "object",
            "properties": {
                "intuition": {"type": "string"},
                "math_explanation": {"type": "string"},
                "market_regime": {"type": "string"},
                "risks": {"type": "string"},
                "usage": {"type": "string"},
            },
            "required": ["intuition", "math_explanation", "market_regime", "risks", "usage"],
        })

        if not response:
            return {"intuition": "Explanation unavailable", "math_explanation": "", "market_regime": "", "risks": "", "usage": ""}

        parsed = self._parse_json_response(response)
        if parsed:
            result = parsed[0] if isinstance(parsed, list) else parsed
            return {
                "intuition": result.get("intuition", ""),
                "math_explanation": result.get("math_explanation", ""),
                "market_regime": result.get("market_regime", ""),
                "risks": result.get("risks", ""),
                "usage": result.get("usage", ""),
            }
        return {"intuition": "Could not parse explanation", "math_explanation": "", "market_regime": "", "risks": "", "usage": ""}
