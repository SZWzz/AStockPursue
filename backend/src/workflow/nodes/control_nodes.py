"""Control-flow and AI Agent nodes — ChatInput, Agent, IF."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)
_AGENT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="wf-agent")


@register_node
class ChatInputNode(BaseNode):
    node_type = "chat_input"; category = "control"; label = "Chat Input"
    description = "Type a natural-language research question for the AI Agent"
    icon = "MessageSquare"
    inputs: List[NodePort] = []
    outputs = [BaseNode.out_port("prompt", PortType.PARAMS)]
    config_schema = {"prompt": {"title": "Prompt", "type": "string", "default": "", "description": "Your research question"}}

    async def execute(self, inputs: dict, config: dict) -> dict:
        prompt = config.get("prompt", "").strip() or "Analyze the market and suggest a trading strategy."
        return {"prompt": {"text": prompt}}


@register_node
class AgentNode(BaseNode):
    """LLM Agent — wraps run_agent_sync() ReAct loop.

    Accepts an optional prompt from a ChatInput node OR a direct prompt in config.
    Upstream context (backtest results, factor data, correlation matrix, etc.) is
    automatically detected and formatted into a structured summary before being
    injected into the prompt via the {context} placeholder.

    Output ports:
        analysis — full agent response text
        code      — extracted SignalEngine Python code (if any)
        factor_suggestion — referenced alpha factor IDs
    """
    node_type = "agent"; category = "control"; label = "AI Agent"
    description = (
        "LLM-powered research agent with full tool access (89 skills). "
        "Connect any upstream node output to 'context' — it will be auto-formatted. "
        "Use {prompt} and {context} placeholders in the prompt template."
    )
    icon = "Bot"; resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("prompt", PortType.PARAMS, required=False,
                         description="Prompt from ChatInput node (optional if prompt is set in config)"),
        BaseNode.in_port("context", PortType.ANY, required=False,
                         description="Any upstream node output — auto-formatted into structured summary"),
    ]
    outputs = [
        BaseNode.out_port("analysis", PortType.PARAMS,
                          description="Full agent response text"),
        BaseNode.out_port("code", PortType.PARAMS,
                          description="Extracted SignalEngine Python code"),
        BaseNode.out_port("factor_suggestion", PortType.PARAMS,
                          description="Referenced alpha factor IDs"),
    ]
    config_schema = {
        "prompt": {
            "title": "Prompt", "type": "string", "default": "",
            "description": "Your research question. Leave empty if using a ChatInput node connected to 'prompt' port.",
        },
        "prompt_template": {
            "title": "Prompt Template", "type": "string", "default": "",
            "description": (
                "Template with {prompt} and {context} placeholders. "
                "Empty = auto: 'Context:\\n{context}\\n\\nTask: {prompt}'. "
                "Example: 'You are a quant analyst. Data:\\n{context}\\n\\nQuestion: {prompt}'"
            ),
        },
        "max_turns": {
            "title": "Max Turns", "type": "integer", "default": 5,
            "minimum": 1, "maximum": 20,
        },
        "system_prompt_override": {
            "title": "System Prompt Override", "type": "string", "default": "",
            "description": "Override the default system prompt. Empty = use default quant analyst persona.",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.agent.loop import run_agent_sync

        # ── Resolve prompt: config takes priority, then ChatInput node ────────
        prompt_text = config.get("prompt", "").strip()
        if not prompt_text:
            prompt_data = inputs.get("prompt", {})
            prompt_text = prompt_data.get("text", "") if isinstance(prompt_data, dict) else str(prompt_data)
        if not prompt_text:
            prompt_text = "Analyze the provided data and give quantitative insights."

        # ── Structured context formatting ─────────────────────────────────────
        context = inputs.get("context")
        context_text = self._format_context(context)

        # ── Apply template ────────────────────────────────────────────────────
        template = config.get("prompt_template", "").strip()
        if template:
            final_prompt = template.replace("{prompt}", prompt_text).replace("{context}", context_text)
        else:
            if context_text:
                final_prompt = f"Context:\n{context_text}\n\nTask: {prompt_text}"
            else:
                final_prompt = prompt_text

        max_turns = int(config.get("max_turns", 5))
        logger.info("Agent: prompt='%.80s...' context_len=%d turns=%d",
                     prompt_text, len(context_text), max_turns)

        try:
            response = await asyncio.get_running_loop().run_in_executor(
                _AGENT_EXECUTOR, lambda: run_agent_sync(final_prompt, max_turns=max_turns),
            )
        except Exception as e:
            logger.exception("Agent failed")
            return {"analysis": {"error": str(e)}, "code": {}, "factor_suggestion": {}}

        if not response:
            return {"analysis": {"text": "No response"}, "code": {}, "factor_suggestion": {}}

        code = self._extract_code(response)
        factor_ids = {"ids": list(set(re.findall(
            r'(alpha101_\d+|gtja191_\d+|qlib158_\d+)', response, re.IGNORECASE)))}

        return {
            "analysis": {"text": response, "length": len(response)},
            "code": code,
            "factor_suggestion": factor_ids,
        }

    # ── Context formatter ─────────────────────────────────────────────────────

    @staticmethod
    def _format_context(context: Any) -> str:
        """Auto-detect upstream data type and produce a structured text summary.

        Intelligently formats common workflow port types:
        - BACKTEST_RESULT → metrics table
        - FACTOR_RESULT → factor list with fitness/IC
        - CORRELATION_MATRIX → summary statistics
        - COMPARISON_RESULT / ATTRIBUTION → report highlights
        - SIGNAL → top allocations
        - DF_FACTOR / DF_OHLCV → shape and column info only (DataFrames are too large)
        - Generic dict → smart sub-dict summarization

        Returns an empty string if context is None or empty.
        """
        if context is None:
            return ""

        # ── dict-like context ─────────────────────────────────────────────────
        if isinstance(context, dict):
            return AgentNode._format_dict_context(context)

        # ── list-like context ─────────────────────────────────────────────────
        if isinstance(context, list):
            if len(context) == 0:
                return ""
            if len(context) > 20:
                return f"[List with {len(context)} items — showing first 5]\n" + \
                       "\n".join(f"  - {AgentNode._brief(v)}" for v in context[:5])
            return "\n".join(f"  - {AgentNode._brief(v)}" for v in context)

        # ── DataFrame context ─────────────────────────────────────────────────
        try:
            import pandas as pd
            if isinstance(context, pd.DataFrame):
                cols = list(context.columns)[:20]
                return (
                    f"[DataFrame: {context.shape[0]} rows × {context.shape[1]} columns]\n"
                    f"Columns ({len(cols)}): {', '.join(str(c)[:30] for c in cols)}\n"
                    f"Date range: {context.index[0]} → {context.index[-1]}"
                )
        except Exception:
            pass

        return str(context)[:500]

    @staticmethod
    def _format_dict_context(data: dict) -> str:
        """Format a dict context by detecting its semantic type."""
        if not data:
            return ""

        # ── Backtest result ───────────────────────────────────────────────────
        if "metrics" in data or "summary" in data:
            return AgentNode._format_backtest_context(data)

        # ── Factor result ─────────────────────────────────────────────────────
        if "factors" in data:
            return AgentNode._format_factor_context(data)

        # ── Correlation matrix ────────────────────────────────────────────────
        if "matrix" in data and "labels" in data:
            return AgentNode._format_correlation_context(data)

        # ── Comparison report ─────────────────────────────────────────────────
        if "winner" in data or "paired_t" in data:
            return AgentNode._format_comparison_context(data)

        # ── Attribution report ────────────────────────────────────────────────
        if "brinson" in data or "factor_attribution" in data:
            return AgentNode._format_attribution_context(data)

        # ── Sentiment data ────────────────────────────────────────────────────
        if "scores" in data:
            scores = data.get("scores", {})
            overall = data.get("overall_mean")
            parts = [f"Sentiment Analysis: {data.get('n_articles', '?')} articles"]
            if overall is not None:
                parts.append(f"Overall mean sentiment: {overall:.3f}")
            if isinstance(scores, dict):
                top = sorted(scores.items(), key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0, reverse=True)[:10]
                parts.append("Top stocks by article count:")
                for sym, info in top:
                    if isinstance(info, dict):
                        parts.append(f"  {sym}: {info.get('count', 0)} articles, mean={info.get('mean_sentiment', '?')}")
                if len(scores) > 10:
                    parts.append(f"  ... and {len(scores) - 10} more stocks")
            return "\n".join(parts)

        # ── Signal data ───────────────────────────────────────────────────────
        if all(isinstance(v, (int, float)) for v in data.values() if v is not None):
            non_zero = {k: v for k, v in data.items() if abs(float(v)) > 0.001}
            if non_zero:
                sorted_signal = sorted(non_zero.items(), key=lambda x: abs(float(x[1])), reverse=True)[:15]
                parts = [f"Trading Signal ({len(data)} codes, {len(non_zero)} active):"]
                for code, weight in sorted_signal:
                    parts.append(f"  {code}: {float(weight):.4f}")
                return "\n".join(parts)

        # ── Generic nested dict → flatten one level ───────────────────────────
        return AgentNode._format_generic_dict(data)

    @staticmethod
    def _format_backtest_context(data: dict) -> str:
        metrics = data.get("metrics", data.get("summary", {}))
        lines = ["Backtest Results:"]
        if isinstance(metrics, dict):
            key_metrics = ["total_return", "annual_return", "sharpe", "max_drawdown",
                           "win_rate", "trade_count", "calmar", "sortino", "volatility"]
            for k in key_metrics:
                if k in metrics and metrics[k] is not None:
                    val = metrics[k]
                    if isinstance(val, float):
                        lines.append(f"  {k}: {val:.4f}")
                    else:
                        lines.append(f"  {k}: {val}")
        if "winner" in data:
            lines.append(f"  Winner: {data['winner']}")
        return "\n".join(lines)

    @staticmethod
    def _format_factor_context(data: dict) -> str:
        factors = data.get("factors", [])
        lines = [f"Factor Results ({len(factors)} factors):"]
        for f in factors[:10]:
            if isinstance(f, dict):
                formula = f.get("formula", f.get("formula_hash", "?"))[:60]
                fitness = f.get("fitness", "?")
                ic = f.get("ic_train") or f.get("ic_test") or "?"
                lines.append(f"  fitness={fitness}, IC={ic} | {formula}")
        if len(factors) > 10:
            lines.append(f"  ... and {len(factors) - 10} more factors")
        if "n_total_evaluated" in data:
            lines.append(f"Total evaluated: {data['n_total_evaluated']}")
        return "\n".join(lines)

    @staticmethod
    def _format_correlation_context(data: dict) -> str:
        labels = data.get("labels", [])
        summary = data.get("summary", {})
        lines = [f"Correlation Matrix: {len(labels)} assets"]
        if summary:
            lines.append(f"  Mean correlation: {summary.get('mean_corr', '?')}")
            lines.append(f"  Max correlation: {summary.get('max_corr', '?')}")
            lines.append(f"  Min correlation: {summary.get('min_corr', '?')}")
            lines.append(f"  Method: {summary.get('method', '?')}, Lookback: {summary.get('lookback_days', '?')} days")
        if labels:
            lines.append(f"  Assets: {', '.join(str(l)[:20] for l in labels[:15])}")
        return "\n".join(lines)

    @staticmethod
    def _format_comparison_context(data: dict) -> str:
        lines = ["Strategy Comparison:"]
        metrics_a = data.get("metrics_a", {})
        metrics_b = data.get("metrics_b", {})
        winner = data.get("winner", {})
        for k in ["sharpe", "total_return", "annual_return", "max_drawdown", "win_rate"]:
            a = metrics_a.get(k)
            b = metrics_b.get(k)
            if a is not None and b is not None:
                w = winner.get(k, "")
                lines.append(f"  {k}: A={a:.4f} vs B={b:.4f} → {w}")
        if "bootstrap" in data:
            b = data["bootstrap"]
            if "prob_a_better_than_b" in b:
                lines.append(f"  Prob(A > B): {b['prob_a_better_than_b']:.2%}")
        if "paired_t" in data:
            t = data["paired_t"]
            if "t_stat" in t:
                lines.append(f"  t-stat: {t['t_stat']:.3f}, mean_diff: {t.get('mean_diff', '?')}")
        return "\n".join(lines)

    @staticmethod
    def _format_attribution_context(data: dict) -> str:
        lines = ["Performance Attribution:"]
        summary = data.get("summary", {})
        if summary:
            for k, v in summary.items():
                lines.append(f"  {k}: {v}")
        for method in ["brinson", "factor_attribution", "sector", "time_series", "tca"]:
            if method in data:
                result = data[method]
                if isinstance(result, dict):
                    if "error" not in result:
                        lines.append(f"  {method}: {AgentNode._brief(result)}")
        return "\n".join(lines)

    @staticmethod
    def _format_generic_dict(data: dict, indent: int = 0) -> str:
        """Flatten a generic nested dict one level, skipping large values."""
        prefix = "  " * indent
        lines = []
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict):
                sub_summary = ", ".join(f"{sk}: {AgentNode._brief(sv)}" for sk, sv in list(v.items())[:6])
                if len(v) > 6:
                    sub_summary += f", ... ({len(v)} keys total)"
                lines.append(f"{prefix}{k}: {{{sub_summary}}}")
            elif isinstance(v, list):
                if len(v) == 0:
                    lines.append(f"{prefix}{k}: []")
                elif len(v) > 5:
                    lines.append(f"{prefix}{k}: [{AgentNode._brief(v[0])}, ... ({len(v)} items)]")
                else:
                    items = ", ".join(AgentNode._brief(x) for x in v)
                    lines.append(f"{prefix}{k}: [{items}]")
            else:
                lines.append(f"{prefix}{k}: {AgentNode._brief(v)}")
        return "\n".join(lines) if lines else str(data)[:500]

    @staticmethod
    def _brief(val: Any) -> str:
        """Short string representation for a value."""
        if val is None:
            return "None"
        if isinstance(val, (int, float)):
            if isinstance(val, float):
                return f"{val:.4f}"
            return str(val)
        if isinstance(val, str):
            return val[:80] + ("..." if len(val) > 80 else "")
        s = str(val)
        return s[:80] + ("..." if len(s) > 80 else "")

    @staticmethod
    def _extract_code(text: str) -> dict:
        m = re.search(r'```python\n(.*?class SignalEngine.*?)```', text, re.DOTALL)
        if m:
            return {"code": m.group(1).strip(), "source": "text_block"}
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
        if m and "def generate" in m.group(1):
            return {"code": m.group(1).strip(), "source": "text_block"}
        return {"code": "", "source": "none"}


@register_node
class IFNode(BaseNode):
    node_type = "if_condition"; category = "control"; label = "IF Condition"
    description = "Route execution based on metric threshold (e.g. Sharpe > 1.0)"
    icon = "GitBranch"
    inputs = [BaseNode.in_port("input", PortType.ANY)]
    outputs = [
        BaseNode.out_port("true_branch", PortType.ANY),
        BaseNode.out_port("false_branch", PortType.ANY),
    ]
    config_schema = {
        "field": {"title": "Metric", "type": "string", "default": "sharpe"},
        "operator": {"title": "Operator", "type": "string", "enum": [">", ">=", "<", "<=", "==", "!="], "default": ">"},
        "threshold": {"title": "Threshold", "type": "number", "default": 0.0},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        data = inputs.get("input", {})
        field = config.get("field", "sharpe")
        threshold = float(config.get("threshold", 0))

        value = None
        if isinstance(data, dict):
            value = (data.get("summary", {}) or {}).get(field) or data.get(field)
            if value is None and "metrics" in data:
                value = data["metrics"].get(field)

        if value is None:
            value = 0

        ops = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: abs(a - b) < 1e-9, "!=": lambda a, b: abs(a - b) >= 1e-9}
        condition = ops.get(config.get("operator", ">"), ops[">"])(float(value), threshold)

        logger.info("IF: %s=%.4f %s %.4f → %s", field, float(value), config.get("operator", ">"), threshold, condition)
        return {"true_branch": data if condition else None, "false_branch": None if condition else data}
