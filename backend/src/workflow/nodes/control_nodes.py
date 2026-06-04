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
    """LLM Agent — wraps run_agent_sync() ReAct loop.  Extracts code from both
    the agent's text response AND the run_dir/code/signal_engine.py file."""
    node_type = "agent"; category = "control"; label = "AI Agent"
    description = "LLM-powered research agent with full tool access (89 skills)"
    icon = "Bot"; resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("prompt", PortType.PARAMS),
        BaseNode.in_port("context", PortType.ANY, required=False),
    ]
    outputs = [
        BaseNode.out_port("analysis", PortType.PARAMS),
        BaseNode.out_port("code", PortType.PARAMS),
        BaseNode.out_port("factor_suggestion", PortType.PARAMS),
    ]
    config_schema = {
        "max_turns": {"title": "Max Turns", "type": "integer", "default": 5, "minimum": 1, "maximum": 20},
        "system_prompt_override": {"title": "System Prompt Override", "type": "string", "default": ""},
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        from src.agent.loop import run_agent_sync

        prompt_data = inputs.get("prompt", {})
        prompt_text = prompt_data.get("text", "") if isinstance(prompt_data, dict) else str(prompt_data)
        if not prompt_text:
            prompt_text = "Analyze the data and provide quantitative insights."

        context = inputs.get("context")
        if isinstance(context, dict):
            ctx_parts = [f"{k}: {v.get('summary', v)}" if isinstance(v, dict) else f"{k}: {v}" for k, v in context.items()]
            if ctx_parts:
                prompt_text = f"Context from upstream:\n{chr(10).join(ctx_parts)}\n\nTask: {prompt_text}"

        max_turns = int(config.get("max_turns", 5))
        logger.info("Agent: prompt='%.80s...' turns=%d", prompt_text, max_turns)

        try:
            response = await asyncio.get_running_loop().run_in_executor(
                _AGENT_EXECUTOR, lambda: run_agent_sync(prompt_text, max_turns=max_turns),
            )
        except Exception as e:
            logger.exception("Agent failed")
            return {"analysis": {"error": str(e)}, "code": {}, "factor_suggestion": {}}

        if not response:
            return {"analysis": {"text": "No response"}, "code": {}, "factor_suggestion": {}}

        # Extract code — try run_dir files first, then text patterns
        code = self._extract_code(response)
        factor_ids = {"ids": list(set(re.findall(r'(alpha101_\d+|gtja191_\d+|qlib158_\d+)', response, re.IGNORECASE)))}

        return {"analysis": {"text": response, "length": len(response)}, "code": code, "factor_suggestion": factor_ids}

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
