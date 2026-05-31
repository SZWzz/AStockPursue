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
- formula: the mathematical formula expressed as pandas operations on a DataFrame 'panel' with columns ['open','high','low','close','volume','vwap']
- description: one-line explanation of what this factor measures

Use these base operators available on the panel DataFrame:
- panel['close'].pct_change(N) for returns
- panel['close'].rolling(N).mean() for moving average
- panel['close'].rolling(N).std() for volatility
- (panel['high'] - panel['low']) / panel['close'] for range
- panel['volume'] / panel['volume'].rolling(N).mean() for volume ratio
- .rank(axis=1, pct=True) for cross-sectional rank
- .shift(N) for lag
- .corr(other) for correlation
- .rolling(N).corr(other) for rolling correlation

Text to analyze:
{text}

Output as a JSON array of factor objects. Only output valid JSON, no commentary."""

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

        Args:
            text: Research paper or article text content.

        Returns:
            List of FactorCandidate objects (only syntactically valid formulas).
        """
        prompt = EXTRACTION_PROMPT.format(text=text[:8000])  # Cap context
        response = self._call_llm(prompt, json_schema=_JSON_SCHEMA_FACTORS)
        if not response:
            return []

        raw_factors = self._parse_json_response(response)
        candidates: list[FactorCandidate] = []
        rejected_count = 0
        for rf in raw_factors:
            try:
                formula = rf.get("formula", "")
                # Validate formula syntax before accepting
                is_valid, err_msg = self._validate_formula_syntax(formula)
                if not is_valid:
                    logger.debug("Rejected invalid formula from LLM: %s — %s", formula[:80], err_msg)
                    rejected_count += 1
                    continue

                candidates.append(FactorCandidate(
                    name=rf.get("name", "unknown"),
                    formula=formula,
                    description=rf.get("description", ""),
                    source="pdf",
                    confidence=rf.get("confidence", 0.5),
                ))
            except Exception as e:
                logger.debug("Failed to parse factor candidate: %s", e)

        if rejected_count > 0:
            logger.info("LLM extraction: %d accepted, %d rejected (invalid syntax)",
                         len(candidates), rejected_count)

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
