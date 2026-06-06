"""AI-powered strategy decomposer — analyse Python code → workflow JSON.

Uses the LLM (via src.agent.loop.run_agent_sync) to analyse a SignalEngine
strategy and produce a {nodes, edges} workflow that can be loaded onto the
canvas.  Includes a self-correction loop: if the output fails validation,
the error is fed back for a retry.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.workflow.node_registry import get_node_registry

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


# ── System prompt builder ──────────────────────────────────────────────────────


def build_decompose_system_prompt() -> str:
    """Build a system prompt that includes the full node registry catalog."""
    registry = get_node_registry()
    definitions = registry.list_all()

    # Build a compact but complete node catalog
    node_catalog_lines: List[str] = []
    for d in sorted(definitions, key=lambda d: (d.category, d.node_type)):
        inputs_str = ", ".join(
            f"{p.name}:{p.port_type.value}" + ("?" if not p.required else "")
            for p in d.inputs
        )
        outputs_str = ", ".join(f"{p.name}:{p.port_type.value}" for p in d.outputs)
        config_str = ", ".join(
            f"{k}({v.get('type','?')})" + (f"={v.get('default','')}" if 'default' in v else "")
            for k, v in d.config_schema.items()
        )
        node_catalog_lines.append(
            f"| `{d.node_type}` | {d.label} | {d.category} | "
            f"IN: {inputs_str or '—'} | OUT: {outputs_str} | "
            f"Config: {config_str or '—'} |"
        )

    catalog = "\n".join(node_catalog_lines)

    return f"""You are a quantitative strategy architect.  Your job is to analyse
Python trading strategy code and decompose it into a visual workflow DAG
using the available node types listed below.

## Available Node Types

| node_type | Label | Category | Inputs | Outputs | Config |
|-----------|-------|----------|--------|---------|--------|
{catalog}

## Rules

1. Every strategy starts with `column_extract` nodes to get `close`/`volume`/etc. from OHLCV data.
2. Connect nodes via their typed ports.  A `DF_FACTOR` output connects to a `DF_FACTOR` input.
3. The final signal should go through `rank_select`/`threshold_select` → `signal_weight` → `rebalance`.
4. For crossover strategies with holding, use `cross_over` + `hold_signal`.
5. Every node needs a unique `id` starting with "n_" (e.g. "n_data", "n_ma5").
6. Edges connect `source` + `source_port` → `target` + `target_port`.
7. Position nodes with x increasing left-to-right (0, 260, 520, …) and y for vertical separation.
8. Use the exact `node_type` and port names from the catalog above.

## Output Format

Reply with ONLY a JSON object (no markdown, no explanation):

{{"nodes": [...], "edges": [...]}}

Each node:
{{"id": "n_xxx", "node_type": "column_extract", "label": "close", "position": {{"x": 0, "y": 0}}, "config": {{"column": "close"}}}}

Each edge:
{{"id": "e_xxx", "source": "n_xxx", "source_port": "series", "target": "n_yyy", "target_port": "series"}}
"""


# ── Decompose function ─────────────────────────────────────────────────────────


def decompose_strategy(code: str) -> Dict[str, Any]:
    """Analyse a Python strategy and return a workflow {nodes, edges} dict.

    Args:
        code: Python source code containing ``class SignalEngine``.

    Returns:
        Dict with ``nodes``, ``edges``, and optionally ``error``.
    """
    if not code or "class SignalEngine" not in code:
        return {"error": "No SignalEngine class found in code", "nodes": [], "edges": []}

    system_prompt = build_decompose_system_prompt()
    user_prompt = f"Decompose this strategy into workflow nodes:\n\n```python\n{code}\n```"

    last_error: Optional[str] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            from src.agent.loop import run_agent_sync

            if last_error and attempt > 0:
                user_prompt = (
                    f"Your previous output had validation errors:\n{last_error}\n\n"
                    f"Please fix and try again.  Original code:\n\n```python\n{code}\n```"
                )

            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
            response = run_agent_sync(full_prompt, max_turns=3)

            if not response:
                last_error = "Agent returned empty response"
                continue

            # Extract JSON from response
            workflow = _extract_workflow_json(response)
            if not workflow:
                last_error = f"Could not extract valid JSON from response: {response[:500]}"
                continue

            # Validate
            errors = _validate_workflow(workflow)
            if errors:
                last_error = "\n".join(errors)
                logger.warning("Decompose attempt %d had %d errors", attempt + 1, len(errors))
                continue

            logger.info("Strategy decomposed successfully in %d attempts", attempt + 1)
            return workflow

        except Exception as e:
            logger.exception("Decompose attempt %d failed", attempt + 1)
            last_error = str(e)

    return {
        "error": f"Failed after {MAX_RETRIES + 1} attempts. Last error: {last_error}",
        "nodes": [],
        "edges": [],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_workflow_json(response: str) -> Optional[Dict[str, Any]]:
    """Extract the workflow JSON from an LLM response (may contain markdown)."""
    # Try direct JSON parse first
    try:
        data = json.loads(response.strip())
        if "nodes" in data and "edges" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            if "nodes" in data and "edges" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try finding outer JSON object
    json_match = re.search(r'\{[\s\S]*"nodes"[\s\S]*"edges"[\s\S]*\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if "nodes" in data and "edges" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None


def _validate_workflow(workflow: Dict[str, Any]) -> List[str]:
    """Basic structural validation of a workflow dict."""
    errors: List[str] = []
    registry = get_node_registry()

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    if not nodes:
        errors.append("Workflow has no nodes")

    # Check node fields
    node_ids = set()
    for n in nodes:
        nid = n.get("id", "")
        if not nid:
            errors.append("Node missing 'id'")
            continue
        node_ids.add(nid)

        ntype = n.get("node_type", "")
        if not ntype:
            errors.append(f"Node {nid} missing 'node_type'")
            continue

        # Validate node type exists in registry
        try:
            registry.get(ntype)
        except KeyError:
            errors.append(f"Node {nid}: unknown node_type '{ntype}'")

    # Check edges
    for e in edges:
        sid = e.get("source", "")
        tid = e.get("target", "")
        if sid and sid not in node_ids:
            errors.append(f"Edge references unknown source node: {sid}")
        if tid and tid not in node_ids:
            errors.append(f"Edge references unknown target node: {tid}")

    return errors


# ── Node catalog for frontend display ─────────────────────────────────────────


def get_node_catalog() -> List[Dict[str, Any]]:
    """Return a simplified node catalog for the frontend decompose UI."""
    registry = get_node_registry()
    return [
        {
            "node_type": d.node_type,
            "category": d.category,
            "label": d.label,
            "description": d.description,
            "inputs": [{"name": p.name, "type": p.port_type.value, "required": p.required} for p in d.inputs],
            "outputs": [{"name": p.name, "type": p.port_type.value} for p in d.outputs],
        }
        for d in sorted(registry.list_all(), key=lambda d: (d.category, d.node_type))
    ]
