"""ExpressionTree → Workflow DAG converter.

Walks an ExpressionTree (from src.factors.mining.expression_tree) and produces
a {nodes, edges} dict that can be loaded directly onto the frontend canvas.

Each ExpressionTree operator maps to one of our atomic factor nodes.  Feature
leaf nodes become ColumnExtractNodes.  Constant leaf nodes become ConstantNodes
that reference an upstream feature for shape alignment.

Usage::

    from src.factors.mining.expression_tree import ExpressionTree
    from src.workflow.tree_converter import expression_tree_to_workflow

    tree: ExpressionTree = ...
    workflow = expression_tree_to_workflow(tree, name="alpha101_001")
    # workflow = {"nodes": [...], "edges": [...]}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)

# ── Operator → workflow node mapping ──────────────────────────────────────────
# Format: (node_type, output_port, input_ports, fixed_config)
# input_ports order matches ExpressionNode.children order.

_OP_MAP: Dict[str, Tuple[str, str, List[str], Dict[str, Any]]] = {
    # ── Arithmetic (binary) ─────────────────────────────────────────────────
    "add":  ("arithmetic", "result", ["a", "b"], {"op": "add"}),
    "sub":  ("arithmetic", "result", ["a", "b"], {"op": "sub"}),
    "mul":  ("arithmetic", "result", ["a", "b"], {"op": "mul"}),
    "div":  ("arithmetic", "result", ["a", "b"], {"op": "div"}),
    "pow":  ("arithmetic", "result", ["a", "b"], {"op": "pow"}),
    # ── Cross-sectional (unary, row-wise) ───────────────────────────────────
    "rank":      ("rank",           "rank",   ["series"], {"ascending": "true"}),
    "cs_zscore": ("scale",          "scaled", ["series"], {"method": "zscore"}),
    "abs":       ("math_transform", "result", ["series"], {"op": "abs"}),
    "log":       ("math_transform", "result", ["series"], {"op": "log"}),
    "sqrt":      ("math_transform", "result", ["series"], {"op": "sqrt"}),
    "neg":       ("math_transform", "result", ["series"], {"op": "neg"}),
    "inv":       ("math_transform", "result", ["series"], {"op": "inv"}),
    "sign":      ("math_transform", "result", ["series"], {"op": "sign"}),
    # ── Time-series rolling (unary + window) ────────────────────────────────
    "ts_mean":   ("ma",                  "ma",     ["series"], {}),
    "ts_std":    ("std_dev",             "std",    ["series"], {}),
    "ts_max":    ("rolling_extremum",    "result", ["series"], {"op": "max"}),
    "ts_min":    ("rolling_extremum",    "result", ["series"], {"op": "min"}),
    "ts_rank":   ("rolling_rank",        "rank",   ["series"], {}),
    "ts_delta":  ("delta",               "delta",  ["series"], {}),
    "ts_delay":  ("delta",               "delta",  ["series"], {}),
    "ts_pct":    ("pct_change",          "returns", ["series"], {}),
    "ts_zscore": ("rolling_scale",       "zscore",  ["series"], {}),
    # ── Binary time-series ──────────────────────────────────────────────────
    "ts_corr":   ("rolling_correlation", "result", ["a", "b"], {"method": "correlation"}),
    "ts_cov":    ("rolling_correlation", "result", ["a", "b"], {"method": "covariance"}),
    # ── Ternary ─────────────────────────────────────────────────────────────
    "if_else":   ("if_else",             "result", ["condition", "true_branch", "false_branch"], {}),
}

# Operators that carry a window parameter from the ExpressionNode
_WINDOW_OPS = {
    "ts_mean", "ts_std", "ts_max", "ts_min", "ts_rank",
    "ts_delta", "ts_delay", "ts_pct", "ts_zscore",
    "ts_corr", "ts_cov",
}

# Feature IDs that map directly to ColumnExtractNode
_FEATURE_COLUMNS = {"open", "high", "low", "close", "volume", "vwap"}

# Operators we cannot yet convert (will be logged)
_UNSUPPORTED_OPS = {"scale", "ts_sum", "ind_neutralize"}

# ── Public API ────────────────────────────────────────────────────────────────


def expression_tree_to_workflow(
    tree: Any,  # ExpressionTree
    name: str = "Factor",
) -> Dict[str, Any]:
    """Convert an ExpressionTree to a workflow {nodes, edges} dict.

    Args:
        tree: An ExpressionTree instance from src.factors.mining.expression_tree.
        name: Display name for the output workflow.

    Returns:
        Dict with ``nodes`` (list of dicts) and ``edges`` (list of dicts)
        suitable for loading onto the frontend canvas.
    """
    root_dict = tree.to_dict()
    ctx = _ConverterCtx()
    root_id = _convert_node(root_dict, ctx)

    # Assign layered layout positions
    _layout(ctx)

    nodes = list(ctx.nodes.values())
    edges = list(ctx.edges)

    logger.info(
        "tree_to_workflow: %s → %d nodes, %d edges",
        name, len(nodes), len(edges),
    )

    return {"nodes": nodes, "edges": edges}


# ── Converter context ─────────────────────────────────────────────────────────


class _ConverterCtx:
    """Mutable context shared across recursive _convert_node calls."""

    def __init__(self):
        self.nodes: Dict[str, dict] = {}   # node_id → node dict
        self.edges: List[dict] = []        # edge dicts
        self._counter: int = 0
        self._feature_cache: Dict[str, str] = {}  # feature_id → node_id
        self._depth: Dict[str, int] = {}   # node_id → tree depth (for layout)

    def new_id(self, prefix: str = "n") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def add_node(self, node_id: str, node_type: str, label: str,
                 config: dict, depth: int) -> None:
        self.nodes[node_id] = {
            "id": node_id,
            "node_type": node_type,
            "label": label,
            "position": {"x": 0, "y": 0},
            "config": config,
        }
        self._depth[node_id] = depth

    def add_edge(self, source_id: str, source_port: str,
                 target_id: str, target_port: str) -> None:
        eid = f"e_{source_id}_{source_port}_{target_id}_{target_port}"
        self.edges.append({
            "id": eid,
            "source": source_id,
            "source_port": source_port,
            "target": target_id,
            "target_port": target_port,
        })


# ── Recursive conversion ──────────────────────────────────────────────────────


def _convert_node(node_dict: dict, ctx: _ConverterCtx, depth: int = 0) -> str:
    """Recursively convert a tree node dict to workflow nodes/edges.

    Returns the workflow node_id of the created node.
    """
    op = node_dict.get("op")
    children: list = node_dict.get("children", [])
    window: Optional[int] = node_dict.get("window")

    # ── Leaf: feature_id ────────────────────────────────────────────────────
    feature_id = node_dict.get("feature_id")
    if feature_id is not None:
        return _handle_feature(feature_id, ctx, depth)

    # ── Leaf: constant value ────────────────────────────────────────────────
    if op is None and "value" in node_dict:
        # Constant leaf — needs a reference input for shape.
        # We'll defer creation; the parent node connects it.
        const_val = float(node_dict["value"])
        return _handle_constant(const_val, ctx, depth)

    # ── Unsupported operator ────────────────────────────────────────────────
    if op in _UNSUPPORTED_OPS:
        logger.warning("tree_converter: unsupported operator %r — skipping subtree", op)
        # Return a fallback: connect the first child directly (skip this node)
        if children:
            return _convert_node(children[0], ctx, depth)
        return ctx.new_id("skipped")

    # ── Unknown operator ────────────────────────────────────────────────────
    if op not in _OP_MAP:
        logger.warning("tree_converter: unknown operator %r", op)
        if children:
            return _convert_node(children[0], ctx, depth)
        return ctx.new_id("unknown")

    # ── Known operator ──────────────────────────────────────────────────────
    node_type, out_port, in_ports, base_config = _OP_MAP[op]
    node_id = ctx.new_id(node_type)

    # Build config
    config = dict(base_config)
    if op in _WINDOW_OPS and window is not None:
        if node_type in ("delta", "pct_change"):
            config["periods"] = window
        else:
            config["window"] = window

    # Build label
    label = _make_label(op, config, window)

    ctx.add_node(node_id, node_type, label, config, depth)

    # Recursively convert children and wire them up
    if len(children) != len(in_ports):
        logger.warning(
            "tree_converter: arity mismatch for %r — expected %d children, got %d",
            op, len(in_ports), len(children),
        )

    for i, child_dict in enumerate(children):
        if i >= len(in_ports):
            break
        child_id = _convert_node(child_dict, ctx, depth + 1)
        target_port = in_ports[i]

        # Determine which output port to use on the child
        child_node = ctx.nodes.get(child_id, {})
        child_type = child_node.get("node_type", "")
        child_out = _get_output_port(child_type)

        ctx.add_edge(child_id, child_out, node_id, target_port)

    return node_id


# ── Leaf handlers ─────────────────────────────────────────────────────────────


def _handle_feature(feature_id: str, ctx: _ConverterCtx, depth: int) -> str:
    """Create (or reuse) a ColumnExtractNode for a feature reference."""
    if feature_id in ctx._feature_cache:
        return ctx._feature_cache[feature_id]

    column = feature_id if feature_id in _FEATURE_COLUMNS else "close"
    node_id = ctx.new_id("feat")
    ctx.add_node(node_id, "column_extract", f"{feature_id}", {"column": column}, depth)
    ctx._feature_cache[feature_id] = node_id
    return node_id


def _handle_constant(value: float, ctx: _ConverterCtx, depth: int) -> str:
    """Create a ConstantNode for a numeric constant.

    The reference input will be wired by the parent's sibling branch,
    so the constant DataFrame has the right shape (dates × codes).
    """
    node_id = ctx.new_id("const")
    label = f"{value:.4g}" if value != int(value) else str(int(value))
    ctx.add_node(node_id, "constant", label, {"constant": value}, depth)
    return node_id


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_output_port(node_type: str) -> str:
    """Get the primary output port name for a node type."""
    port_map: Dict[str, str] = {
        "column_extract":    "series",
        "ma":                "ma",
        "ema":               "ema",
        "delta":             "delta",
        "pct_change":        "returns",
        "std_dev":           "std",
        "rank":              "rank",
        "scale":             "scaled",
        "arithmetic":        "result",
        "extremum":          "result",
        "cross_over":        "signal",
        "compare":           "result",
        "bool_combine":      "result",
        "bool_not":          "result",
        "math_transform":    "result",
        "rolling_extremum":  "result",
        "rolling_rank":      "rank",
        "rolling_scale":     "zscore",
        "rolling_correlation": "result",
        "if_else":           "result",
        "constant":          "value",
    }
    return port_map.get(node_type, "result")


def _make_label(op: str, config: dict, window: Optional[int]) -> str:
    """Create a human-readable label for the node."""
    op_labels: Dict[str, str] = {
        "add": "+", "sub": "−", "mul": "×", "div": "÷", "pow": "^",
        "rank": "Rank", "cs_zscore": "ZScore",
        "abs": "|x|", "log": "log", "sqrt": "√", "neg": "−x", "inv": "1/x", "sign": "sign",
        "ts_mean": "MA", "ts_std": "Std", "ts_max": "RollMax", "ts_min": "RollMin",
        "ts_rank": "RollRank", "ts_delta": "Δ", "ts_delay": "Delay", "ts_pct": "Δ%",
        "ts_zscore": "RollZ",
        "ts_corr": "Corr", "ts_cov": "Cov",
        "if_else": "If",
    }
    base = op_labels.get(op, op)
    # Show window/periods from either the window param or config
    effective_window = window
    if effective_window is None:
        effective_window = config.get("window") or config.get("periods")
    if effective_window is not None and op in _WINDOW_OPS:
        return f"{base}({effective_window})"
    if op in ("add", "sub", "mul", "div", "pow"):
        return op_labels[op]
    return base


def _layout(ctx: _ConverterCtx, x_spacing: float = 260, y_spacing: float = 100):
    """Assign (x, y) positions in a layered layout based on tree depth.

    Nodes at the same depth share the same x coordinate.  Y coordinates
    are spread to avoid overlap within the same depth layer.
    """
    # Group nodes by depth
    depth_buckets: Dict[int, List[str]] = {}
    for nid, d in ctx._depth.items():
        depth_buckets.setdefault(d, []).append(nid)

    max_depth = max(depth_buckets) if depth_buckets else 0

    for depth, node_ids in sorted(depth_buckets.items()):
        # x: deepest nodes on the left (raw data), root on the right
        x = (max_depth - depth) * x_spacing
        n = len(node_ids)
        for i, nid in enumerate(node_ids):
            y = (i - (n - 1) / 2) * y_spacing
            ctx.nodes[nid]["position"] = {"x": x, "y": y}
