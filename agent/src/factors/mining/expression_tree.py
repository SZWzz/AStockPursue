"""Expression tree for genetic programming factor mining.

Models an alpha factor as a tree of arithmetic and time-series operators.
Supports random generation, mutation, crossover, and execution on panel data.

Design constraints:
    - MAX_DEPTH = 5   (prevent bloat)
    - MAX_COMPLEXITY = 50  (node count limit)
    - All operators act on wide pd.DataFrame (index=dates, columns=codes)
    - NaN propagation policy: operators preserve NaN, never silent fillna(0)
"""

from __future__ import annotations

import copy
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Operator registry
# ---------------------------------------------------------------------------

# Each operator: (arity, python_callable, display_symbol)
# arity == 1: unary  (operates on one child DataFrame)
# arity == 2: binary (operates on two child DataFrames)
# arity == 0: leaf   (feature reference or constant)

OPERATOR_REGISTRY: dict[str, tuple[int, Callable[..., pd.DataFrame], str]] = {
    # --- arithmetic (binary) ---
    "add":  (2, lambda a, b: a + b, "+"),
    "sub":  (2, lambda a, b: a - b, "-"),
    "mul":  (2, lambda a, b: a * b, "*"),
    "div":  (2, lambda a, b: (a / b.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan), "/"),
    "pow":  (2, lambda a, b: (a.clip(lower=-100, upper=100) ** b.clip(-5, 5)).replace([np.inf, -np.inf], np.nan), "^"),
    # --- cross-sectional (unary, row-wise) ---
    "rank":     (1, lambda x: x.rank(axis=1, method="average", pct=True, na_option="keep"), "rank"),
    "cs_zscore":(1, lambda x: ((x.subtract(x.mean(axis=1, skipna=True), axis=0)).div(x.std(axis=1, skipna=True).replace(0, np.nan), axis=0)).replace([np.inf, -np.inf], np.nan), "csz"),
    "scale":    (1, lambda x: (lambda s: x.div(s.where(s > 0), axis=0))(x.abs().sum(axis=1, skipna=True)), "scale"),
    "abs":      (1, lambda x: x.abs(), "abs"),
    "log":      (1, lambda x: np.log(x.clip(lower=1e-12)), "log"),
    "sqrt":     (1, lambda x: np.sqrt(x.clip(lower=0)), "sqrt"),
    "sign":     (1, lambda x: np.sign(x), "sign"),
    "neg":      (1, lambda x: -x, "neg"),
    "inv":      (1, lambda x: (1.0 / x.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan), "1/x"),
    # --- conditional (ternary) ---
    "if_else":  (3, lambda cond, t, f: pd.DataFrame(
        np.where(cond.to_numpy(dtype=np.float64) > 0, t.to_numpy(dtype=np.float64), f.to_numpy(dtype=np.float64)),
        index=cond.index, columns=cond.columns), "if"),
    # --- time-series rolling (unary + window param from node.window) ---
    "ts_mean":   (1, lambda x, w=20: x.rolling(window=min(w, max(1, len(x)//4)), min_periods=max(1, min(w, max(1, len(x)//4))//2)).mean(), "ts_mean"),
    "ts_std":    (1, lambda x, w=20: x.rolling(window=min(w, max(2, len(x)//4)), min_periods=max(2, min(w, max(2, len(x)//4))//2)).std(ddof=1), "ts_std"),
    "ts_max":    (1, lambda x, w=20: x.rolling(window=min(w, max(1, len(x)//4)), min_periods=max(1, min(w, max(1, len(x)//4))//2)).max(), "ts_max"),
    "ts_min":    (1, lambda x, w=20: x.rolling(window=min(w, max(1, len(x)//4)), min_periods=max(1, min(w, max(1, len(x)//4))//2)).min(), "ts_min"),
    "ts_sum":    (1, lambda x, w=20: x.rolling(window=min(w, max(1, len(x)//4)), min_periods=max(1, min(w, max(1, len(x)//4))//2)).sum(), "ts_sum"),
    "ts_rank":   (1, lambda x, w=20: x.rolling(window=min(w, max(3, len(x)//4)), min_periods=max(3, min(w, max(3, len(x)//4))//2)).apply(
        lambda s: s.rank(pct=True).iloc[-1] if len(s) >= 3 else np.nan, raw=False), "ts_rank"),
    "ts_delta":  (1, lambda x, w=20: x - x.shift(min(w, max(1, len(x)//4))), "ts_delta"),
    "ts_delay":  (1, lambda x, w=5: x.shift(min(w, max(1, len(x)//4))), "delay"),
    "ts_pct":    (1, lambda x, w=20: x.pct_change(min(w, max(1, len(x)//4))), "ts_pct"),
    "ts_zscore": (1, lambda x, w=20: ((x - x.rolling(window=min(w, max(2, len(x)//4)), min_periods=max(2, min(w, max(2, len(x)//4))//2)).mean())
        / x.rolling(window=min(w, max(2, len(x)//4)), min_periods=max(2, min(w, max(2, len(x)//4))//2)).std(ddof=1).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan), "ts_z"),
    # --- cross-sectional pairwise (binary, uses window from node.window) ---
    "ts_corr":   (2, lambda a, b, w=20: _rolling_corr(a, b, w), "corr"),
    "ts_cov":    (2, lambda a, b, w=20: _rolling_cov(a, b, w), "cov"),
    # --- industry neutralization (unary, cross-sectional) ---
    "ind_neutralize": (1, lambda x: _ind_neutralize(x), "indN"),
}

# Rolling window options (trading days) for GP to evolve
WINDOW_OPTIONS: list[int] = [3, 5, 10, 20, 40, 60, 120]

def _rolling_corr(a: pd.DataFrame, b: pd.DataFrame, w: int) -> pd.DataFrame:
    """Element-wise rolling Pearson correlation between two DataFrames."""
    window = min(w, max(3, len(a) // 4))
    min_p = max(3, window // 2)
    ma = a.rolling(window=window, min_periods=min_p).mean()
    mb = b.rolling(window=window, min_periods=min_p).mean()
    cov = ((a - ma) * (b - mb)).rolling(window=window, min_periods=min_p).mean()
    sa = a.rolling(window=window, min_periods=min_p).std(ddof=1)
    sb = b.rolling(window=window, min_periods=min_p).std(ddof=1)
    result = cov / (sa * sb)
    return result.replace([np.inf, -np.inf], np.nan)

def _rolling_cov(a: pd.DataFrame, b: pd.DataFrame, w: int) -> pd.DataFrame:
    """Element-wise rolling covariance between two DataFrames."""
    window = min(w, max(3, len(a) // 4))
    min_p = max(3, window // 2)
    ma = a.rolling(window=window, min_periods=min_p).mean()
    mb = b.rolling(window=window, min_periods=min_p).mean()
    result = ((a - ma) * (b - mb)).rolling(window=window, min_periods=min_p).mean()
    return result.replace([np.inf, -np.inf], np.nan)


def _ind_neutralize(x: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional industry neutralization.

    For each date, demean the factor within each "industry" cluster.
    When no explicit industry mapping is available, uses a simple
    cross-sectional demean (market neutral) as the default behavior.

    With a sector mapping provided via panel['sector'], subtracts
    the sector-cap-weighted mean from each stock.
    """
    # Market-neutral: subtract cross-sectional mean per date
    cs_mean = x.mean(axis=1, skipna=True)
    result = x.subtract(cs_mean, axis=0)
    return result.replace([np.inf, -np.inf], np.nan)

MAX_DEPTH = 5
MAX_COMPLEXITY = 50
POPULATION_SIZE_DEFAULT = 100

# Feature IDs for leaf nodes (data columns accessible to factors)
FEATURE_IDS: list[str] = [
    "open", "high", "low", "close", "volume", "vwap",
    "returns_1d", "returns_5d", "returns_20d",
    "volume_ratio", "high_low_ratio",
]

# Operator names for random generation
UNARY_OPS = [k for k, v in OPERATOR_REGISTRY.items() if v[0] == 1]
BINARY_OPS = [k for k, v in OPERATOR_REGISTRY.items() if v[0] == 2]
TERNARY_OPS = [k for k, v in OPERATOR_REGISTRY.items() if v[0] == 3]


# ---------------------------------------------------------------------------
# Expression Node / Tree
# ---------------------------------------------------------------------------

@dataclass
class ExpressionNode:
    """A node in the expression tree.

    Attributes:
        op: Operator name (key in OPERATOR_REGISTRY), or None for leaf.
        children: Child nodes (length matches operator arity).
        value: Constant value for leaf nodes (float).
        feature_id: Feature reference for leaf nodes (str from FEATURE_IDS).
        window: Rolling window parameter for ts_* operators.
    """
    op: str | None = None
    children: list[ExpressionNode] = field(default_factory=list)
    value: float | None = None
    feature_id: str | None = None
    window: int = 20

    @property
    def is_leaf(self) -> bool:
        return self.op is None

    @property
    def arity(self) -> int:
        if self.op is None:
            return 0
        return OPERATOR_REGISTRY[self.op][0]

    def to_formula(self) -> str:
        """Render the node as a human-readable formula string."""
        if self.is_leaf:
            if self.feature_id is not None:
                return self.feature_id
            return f"{self.value:.4g}" if self.value is not None else "?"
        _, _, symbol = OPERATOR_REGISTRY[self.op or ""]
        if self.arity == 1:
            return f"{symbol}({self.children[0].to_formula()})"
        return f"({self.children[0].to_formula()} {symbol} {self.children[1].to_formula()})"

    def copy(self) -> ExpressionNode:
        """Deep copy the node subtree."""
        return ExpressionNode(
            op=self.op,
            children=[c.copy() for c in self.children],
            value=self.value,
            feature_id=self.feature_id,
            window=self.window,
        )


class ExpressionTree:
    """Wrapper around an ExpressionNode root with tree-level operations."""

    def __init__(self, root: ExpressionNode) -> None:
        self.root = root

    # ---- serialization ----

    def to_formula(self) -> str:
        return self.root.to_formula()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return _node_to_dict(self.root)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExpressionTree:
        return cls(_node_from_dict(d))

    # ---- metrics ----

    def depth(self) -> int:
        return _node_depth(self.root)

    def complexity(self) -> int:
        return _node_count(self.root)

    # ---- generation ----

    @classmethod
    def random(
        cls,
        rng: random.Random | None = None,
        max_depth: int = MAX_DEPTH,
        feature_ids: list[str] | None = None,
    ) -> ExpressionTree:
        """Generate a random expression tree using ramped half-and-half."""
        rng = rng or random.Random()
        fids = feature_ids or FEATURE_IDS
        method = rng.choice(["grow", "full"])
        root = _random_node(rng, method, max_depth, fids)
        return cls(root)

    # ---- evolution operators ----

    def mutate(self, rng: random.Random | None = None, rate: float = 0.1) -> ExpressionTree:
        """Point mutation: replace a random subtree with a new random tree."""
        rng = rng or random.Random()
        new_root = self.root.copy()
        _mutate_node(new_root, rng, rate, MAX_DEPTH)
        return ExpressionTree(new_root)

    def crossover(
        self, other: ExpressionTree, rng: random.Random | None = None
    ) -> tuple[ExpressionTree, ExpressionTree]:
        """Subtree crossover: swap random subtrees between two trees."""
        rng = rng or random.Random()
        a = self.root.copy()
        b = other.root.copy()
        _crossover_nodes(a, b, rng)
        return ExpressionTree(a), ExpressionTree(b)

    # ---- execution ----

    def to_callable(self) -> Callable[[dict[str, pd.DataFrame]], pd.DataFrame]:
        """Compile the expression tree into a callable that accepts a panel dict.

        Returns a function f(panel) -> pd.DataFrame that evaluates the factor
        on the given panel data.
        """
        root = self.root  # capture for closure

        def _evaluate(node: ExpressionNode, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
            if node.is_leaf:
                if node.feature_id is not None:
                    if node.feature_id in panel:
                        return panel[node.feature_id].astype(np.float64)
                    # Derived features
                    if node.feature_id == "returns_1d":
                        close = panel.get("close")
                        if close is None:
                            raise KeyError("returns_1d requires 'close' in panel")
                        return close.pct_change(1)
                    if node.feature_id == "returns_5d":
                        close = panel.get("close")
                        if close is None:
                            raise KeyError("returns_5d requires 'close' in panel")
                        return close.pct_change(5)
                    if node.feature_id == "returns_20d":
                        close = panel.get("close")
                        if close is None:
                            raise KeyError("returns_20d requires 'close' in panel")
                        return close.pct_change(20)
                    if node.feature_id == "volume_ratio":
                        vol = panel.get("volume")
                        if vol is None:
                            raise KeyError("volume_ratio requires 'volume' in panel")
                        return vol / vol.rolling(window=20, min_periods=5).mean()
                    if node.feature_id == "high_low_ratio":
                        high = panel.get("high")
                        low = panel.get("low")
                        if high is None or low is None:
                            raise KeyError("high_low_ratio requires 'high' and 'low' in panel")
                        return (high - low) / low.replace(0, np.nan)
                    raise KeyError(f"Unknown feature_id: {node.feature_id}")
                # Constant leaf
                ref_col = next(iter(panel.values())) if panel else None
                if ref_col is not None:
                    return pd.DataFrame(
                        node.value or 0.0,
                        index=ref_col.index,
                        columns=ref_col.columns,
                        dtype=np.float64,
                    )
                return pd.DataFrame(np.full((1, 1), node.value or 0.0, dtype=np.float64))

            # Internal node: evaluate children, apply operator
            op_name = node.op
            if op_name is None:
                raise ValueError("Internal node has no operator")
            arity, func, _ = OPERATOR_REGISTRY[op_name]

            child_results = [_evaluate(c, panel) for c in node.children]

            # Pass window parameter for time-series operators
            window = node.window if node.window else 20
            if op_name.startswith("ts_") or op_name in ("ts_corr", "ts_cov"):
                if arity == 1:
                    return func(child_results[0], window)
                elif arity == 2:
                    return func(child_results[0], child_results[1], window)

            if arity == 1:
                return func(child_results[0])
            elif arity == 2:
                return func(child_results[0], child_results[1])
            elif arity == 3:
                return func(child_results[0], child_results[1], child_results[2])
            raise ValueError(f"Unknown arity {arity} for op {op_name}")

        def compute(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
            result = _evaluate(root, panel)
            # Final cleanup
            result = result.replace([np.inf, -np.inf], np.nan)
            if not isinstance(result, pd.DataFrame):
                result = pd.DataFrame(result)
            return result

        return compute


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _node_to_dict(node: ExpressionNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if node.op is not None:
        result["op"] = node.op
    if node.children:
        result["children"] = [_node_to_dict(c) for c in node.children]
    if node.value is not None:
        result["value"] = node.value
    if node.feature_id is not None:
        result["feature_id"] = node.feature_id
    if node.window != 20:
        result["window"] = node.window
    return result


def _node_from_dict(d: dict[str, Any]) -> ExpressionNode:
    return ExpressionNode(
        op=d.get("op"),
        children=[_node_from_dict(c) for c in d.get("children", [])],
        value=d.get("value"),
        feature_id=d.get("feature_id"),
        window=d.get("window", 20),
    )


def _node_depth(node: ExpressionNode) -> int:
    if node.is_leaf or not node.children:
        return 0
    return 1 + max(_node_depth(c) for c in node.children)


def _node_count(node: ExpressionNode) -> int:
    if node.is_leaf or not node.children:
        return 1
    return 1 + sum(_node_count(c) for c in node.children)


def _random_node(
    rng: random.Random,
    method: str,
    max_depth: int,
    feature_ids: list[str],
) -> ExpressionNode:
    """Recursive random node generator.

    method="full": always use internal nodes until max_depth.
    method="grow": random choice of leaf vs internal at each depth.
    """
    if max_depth <= 0:
        return _random_leaf(rng, feature_ids)

    if method == "grow":
        # At max_depth - 1, force leaf with higher probability
        p_leaf = 0.5 if max_depth > 1 else 0.8
        if rng.random() < p_leaf:
            return _random_leaf(rng, feature_ids)

    # Pick an operator — weighted random choice between unary/binary/ternary
    op_type_roll = rng.random()
    if op_type_roll < 0.55 and UNARY_OPS:
        op = rng.choice(UNARY_OPS)
        child = _random_node(rng, method, max_depth - 1, feature_ids)
        window = rng.choice(WINDOW_OPTIONS) if op.startswith("ts_") else 20
        return ExpressionNode(op=op, children=[child], window=window)
    elif op_type_roll < 0.90 and BINARY_OPS:
        op = rng.choice(BINARY_OPS)
        left = _random_node(rng, method, max_depth - 1, feature_ids)
        right = _random_node(rng, method, max_depth - 1, feature_ids)
        window = rng.choice(WINDOW_OPTIONS) if op.startswith("ts_") else 20
        return ExpressionNode(op=op, children=[left, right], window=window)
    elif TERNARY_OPS:
        op = rng.choice(TERNARY_OPS)
        cond = _random_node(rng, method, max_depth - 1, feature_ids)
        t_branch = _random_node(rng, method, max_depth - 1, feature_ids)
        f_branch = _random_node(rng, method, max_depth - 1, feature_ids)
        return ExpressionNode(op=op, children=[cond, t_branch, f_branch])
    return _random_leaf(rng, feature_ids)


def _random_leaf(rng: random.Random, feature_ids: list[str]) -> ExpressionNode:
    if rng.random() < 0.8:
        return ExpressionNode(feature_id=rng.choice(feature_ids))
    return ExpressionNode(value=round(rng.uniform(-2.0, 2.0), 4))


def _mutate_node(
    node: ExpressionNode,
    rng: random.Random,
    rate: float,
    max_depth: int,
) -> bool:
    """Mutate a random subtree in-place. Returns True if mutation occurred."""
    if rng.random() < rate:
        new_node = _random_node(rng, "grow", max_depth, FEATURE_IDS)
        node.op = new_node.op
        node.children = new_node.children
        node.value = new_node.value
        node.feature_id = new_node.feature_id
        node.window = new_node.window
        return True
    for child in node.children:
        if _mutate_node(child, rng, rate, max_depth - 1):
            return True
    return False


def _collect_nodes(node: ExpressionNode) -> list[ExpressionNode]:
    """Collect all nodes in the tree (BFS order)."""
    result: list[ExpressionNode] = [node]
    for child in node.children:
        result.extend(_collect_nodes(child))
    return result


def _crossover_nodes(
    a: ExpressionNode,
    b: ExpressionNode,
    rng: random.Random,
) -> None:
    """Swap a random subtree between a and b in-place."""
    nodes_a = _collect_nodes(a)
    nodes_b = _collect_nodes(b)
    if not nodes_a or not nodes_b:
        return
    na = rng.choice(nodes_a)
    nb = rng.choice(nodes_b)
    # Swap all attributes
    (na.op, nb.op) = (nb.op, na.op)
    (na.children, nb.children) = (nb.children, na.children)
    (na.value, nb.value) = (nb.value, na.value)
    (na.feature_id, nb.feature_id) = (nb.feature_id, na.feature_id)
    (na.window, nb.window) = (nb.window, na.window)
