"""Expression tree for genetic programming factor mining.

Models an alpha factor as a tree of arithmetic and time-series operators.
Supports random generation, mutation, crossover, and execution on panel data.

**Formula consistency contract** (single source of truth):
    ExpressionTree (or its JSON dict form) is the authoritative representation.
    All derived forms MUST be generated from it, never authored independently:

        ExpressionTree
        ├── to_formula()        → human-readable string
        ├── normalized_formula  → canonical string (sorted args, fixed names)
        ├── formula_hash        → SHA256(normalized_formula) for dedup
        ├── to_dict()           → JSON-serializable dict
        ├── to_signalengine_code() → executable Python SignalEngine code
        └── to_callable()       → in-memory callable for GP evaluation

Design constraints:
    - MAX_DEPTH = 5   (prevent bloat)
    - MAX_COMPLEXITY = 50  (node count limit)
    - All operators act on wide pd.DataFrame (index=dates, columns=codes)
    - NaN propagation policy: operators preserve NaN, never silent fillna(0)
"""

from __future__ import annotations

import copy
import hashlib
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Operator registry with tier metadata
# ---------------------------------------------------------------------------

# Operator tier definitions for progressive unlocking during GP evolution.
# basic:     available from generation 0 (60% of total generations)
# advanced:  unlocked at 40% progress
# alternative: unlocked at 80% progress
OPERATOR_TIERS: dict[str, str] = {
    # ── basic: arithmetic + simple rolling + cross-sectional ──
    "add": "basic", "sub": "basic", "mul": "basic", "div": "basic",
    "rank": "basic", "abs": "basic", "log": "basic", "sqrt": "basic",
    "sign": "basic", "neg": "basic",
    "ts_mean": "basic", "ts_std": "basic", "ts_max": "basic", "ts_min": "basic",
    "ts_delta": "basic", "ts_delay": "basic", "ts_pct": "basic",
    # ── advanced: time-series statistics + cross-sectional regression ──
    "ts_sum": "advanced", "ts_rank": "advanced", "ts_zscore": "advanced",
    "cs_zscore": "advanced", "scale": "advanced",
    "ts_corr": "advanced", "ts_cov": "advanced", "pow": "advanced", "inv": "advanced",
    # ── alternative: conditional + industry neutralization + text/flow ──
    "if_else": "alternative", "ind_neutralize": "alternative",
}

TIER_UNLOCK_ORDER: dict[str, int] = {"basic": 0, "advanced": 1, "alternative": 2}

def get_allowed_operators(generation: int, total_generations: int) -> list[str]:
    """Return the set of operator names allowed at a given evolution progress.

    Args:
        generation: Current generation number (0-indexed).
        total_generations: Total number of generations planned.

    Returns:
        List of allowed operator names.
    """
    progress = generation / max(total_generations, 1)
    allowed: list[str] = []
    for op, tier in OPERATOR_TIERS.items():
        tier_idx = TIER_UNLOCK_ORDER.get(tier, 0)
        if tier_idx == 0 or (tier_idx == 1 and progress > 0.4) or (tier_idx == 2 and progress > 0.8):
            allowed.append(op)
    return allowed


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
    """Wrapper around an ExpressionNode root with tree-level operations.

    **Formula consistency**: this tree is the single source of truth.
    All derived forms (formula string, hash, SignalEngine code, dict)
    are generated from it — never authored independently.
    """

    def __init__(self, root: ExpressionNode) -> None:
        self.root = root

    # ---- serialization ----

    def to_formula(self) -> str:
        return self.root.to_formula()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict (the authoritative serialization)."""
        return _node_to_dict(self.root)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExpressionTree:
        """Deserialize from JSON-compatible dict."""
        return cls(_node_from_dict(d))

    # ---- formula consistency (single source of truth) ----

    @property
    def normalized_formula(self) -> str:
        """Canonical, deterministic formula string for hashing and dedup.

        Normalization rules:
        - Binary commutative operators (add, mul) sort children alphabetically
        - Feature IDs lowercased
        - Window values always included for ts_* operators
        - Whitespace normalized
        - Constants rounded to 6 decimal places
        """
        return _normalize_node(self.root)

    @property
    def formula_hash(self) -> str:
        """SHA256 hash of the normalized formula — used for dedup across the system.

        Two trees with the same mathematical meaning produce the same hash,
        even if they were generated with different variable names or
        child ordering for commutative operators.
        """
        return hashlib.sha256(self.normalized_formula.encode("utf-8")).hexdigest()[:16]

    # ---- SignalEngine code generation ----

    def to_signalengine_code(self, class_name: str = "GeneratedSignal") -> str:
        """Compile the expression tree into a standard SignalEngine Python class.

        The generated code follows the exact SignalEngine contract:
            class SignalEngine:
                def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:

        This ensures the factor can be used directly in backtests without
        any code modification — the formula is embedded as the canonical
        implementation.

        Args:
            class_name: Name for the generated SignalEngine class.

        Returns:
            Complete Python source code string.
        """
        return _compile_to_signalengine(self.root, class_name)

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


# ---------------------------------------------------------------------------
# Formula normalization — canonical string for hashing / dedup
# ---------------------------------------------------------------------------

# Commutative operators: child order doesn't matter, so we sort children
# to get a deterministic canonical form.
_COMMUTATIVE_OPS = {"add", "mul"}


def _normalize_node(node: ExpressionNode) -> str:
    """Generate a canonical, deterministic formula string for hashing.

    This is the foundation of formula consistency — all hash-based dedup
    uses this normalized form so that semantically identical formulas
    (differing only in child ordering or whitespace) produce the same hash.
    """
    if node.is_leaf:
        if node.feature_id is not None:
            return node.feature_id.lower()
        if node.value is not None:
            return f"{node.value:.6g}"
        return "?"

    op = node.op or "?"
    _, _, symbol = OPERATOR_REGISTRY.get(op, (0, lambda x: x, op))

    child_strs = [_normalize_node(c) for c in node.children]

    # Sort children for commutative operators
    if op in _COMMUTATIVE_OPS:
        child_strs.sort()

    # Time-series operators: include window in canonical form
    if op.startswith("ts_") or op in ("ts_corr", "ts_cov"):
        w = node.window if node.window else 20
        return f"{symbol}({','.join(child_strs)},w={w})"

    if node.arity == 1:
        return f"{symbol}({child_strs[0]})"
    elif node.arity == 2:
        return f"({child_strs[0]}{symbol}{child_strs[1]})"
    elif node.arity == 3:
        return f"{symbol}({','.join(child_strs)})"
    return f"{symbol}({','.join(child_strs)})"


# ---------------------------------------------------------------------------
# SignalEngine code compiler — ExpressionTree → executable Python
# ---------------------------------------------------------------------------

# Mapping from expression tree operators to pandas/SignalEngine code patterns.
# Each entry is a lambda that takes child code strings + window and returns
# a complete expression string.
_SIGNALENGINE_OP_MAP: dict[str, Callable[..., str]] = {
    # arithmetic
    "add":  lambda a, b, w: f"({a} + {b})",
    "sub":  lambda a, b, w: f"({a} - {b})",
    "mul":  lambda a, b, w: f"({a} * {b})",
    "div":  lambda a, b, w: f"({a} / {b}.replace(0, np.nan))",
    "pow":  lambda a, b, w: f"({a}.clip(-100, 100) ** {b}.clip(-5, 5))",
    # cross-sectional
    "rank":      lambda x, _, w: f"{x}.rank(axis=1, pct=True, na_option='keep')",
    "cs_zscore": lambda x, _, w: f"(({x}.sub({x}.mean(axis=1), axis=0)).div({x}.std(axis=1).replace(0, np.nan), axis=0))",
    "scale":     lambda x, _, w: f"({x}.div({x}.abs().sum(axis=1).replace(0, np.nan), axis=0))",
    "abs":       lambda x, _, w: f"{x}.abs()",
    "log":       lambda x, _, w: f"np.log({x}.clip(1e-12))",
    "sqrt":      lambda x, _, w: f"np.sqrt({x}.clip(0))",
    "sign":      lambda x, _, w: f"np.sign({x})",
    "neg":       lambda x, _, w: f"(-{x})",
    "inv":       lambda x, _, w: f"(1.0 / {x}.replace(0, np.nan))",
    # conditional
    "if_else":   lambda c, t, f, w: f"pd.DataFrame(np.where({c}.values > 0, {t}.values, {f}.values), index={c}.index, columns={c}.columns)",
    # time-series rolling
    "ts_mean":   lambda x, _, w: f"{x}.rolling({w}, min_periods=max(1,{w}//2)).mean()",
    "ts_std":    lambda x, _, w: f"{x}.rolling({w}, min_periods=max(2,{w}//2)).std()",
    "ts_max":    lambda x, _, w: f"{x}.rolling({w}, min_periods=max(1,{w}//2)).max()",
    "ts_min":    lambda x, _, w: f"{x}.rolling({w}, min_periods=max(1,{w}//2)).min()",
    "ts_sum":    lambda x, _, w: f"{x}.rolling({w}, min_periods=max(1,{w}//2)).sum()",
    "ts_rank":   lambda x, _, w: f"{x}.rolling({w}, min_periods=max(3,{w}//2)).apply(lambda s: s.rank(pct=True).iloc[-1] if len(s)>=3 else np.nan)",
    "ts_delta":  lambda x, _, w: f"({x} - {x}.shift({w}))",
    "ts_delay":  lambda x, _, w: f"{x}.shift({w})",
    "ts_pct":    lambda x, _, w: f"{x}.pct_change({w})",
    "ts_zscore": lambda x, _, w: f"(({x} - {x}.rolling({w}, min_periods=max(2,{w}//2)).mean()) / {x}.rolling({w}, min_periods=max(2,{w}//2)).std().replace(0, np.nan))",
    # cross-sectional pairwise
    "ts_corr": lambda a, b, w: f"_rolling_corr({a}, {b}, {w})",
    "ts_cov":  lambda a, b, w: f"_rolling_cov({a}, {b}, {w})",
    # industry neutralization
    "ind_neutralize": lambda x, _, w: f"({x}.sub({x}.mean(axis=1), axis=0))",
}


def _compile_node_to_code(node: ExpressionNode) -> str:
    """Recursively compile an ExpressionNode to a pandas code string.

    The generated code uses the same logic as ``to_callable()`` but produces
    readable, importable Python source code instead of a closure.
    """
    if node.is_leaf:
        if node.feature_id is not None:
            return f"df['{node.feature_id}']"
        return f"{node.value:.6g}" if node.value is not None else "0.0"

    op = node.op
    if op is None:
        raise ValueError("Internal node has no operator")

    child_codes = [_compile_node_to_code(c) for c in node.children]
    window = node.window if node.window else 20

    code_gen = _SIGNALENGINE_OP_MAP.get(op)
    if code_gen is None:
        raise ValueError(f"No SignalEngine code mapping for operator: {op}")

    if op in ("if_else",):
        return code_gen(*child_codes, window)
    elif op in ("ts_corr", "ts_cov"):
        return code_gen(child_codes[0], child_codes[1], window)
    elif node.arity == 1:
        return code_gen(child_codes[0], "", window)
    elif node.arity == 2:
        return code_gen(child_codes[0], child_codes[1], window)
    elif node.arity == 3:
        return code_gen(*child_codes, window)
    raise ValueError(f"Unknown arity {node.arity} for op {op}")


def _compile_to_signalengine(root: ExpressionNode, class_name: str = "GeneratedSignal") -> str:
    """Compile an ExpressionNode tree into a complete SignalEngine Python class.

    The generated code is a STANDARD SignalEngine implementation that can be
    directly written to ``code/signal_engine.py`` and used in backtests.

    Formula consistency: the expression embedded in the generated code IS the
    compiled form of this tree — not a separately authored string.
    """
    factor_expr = _compile_node_to_code(root)
    formula_str = root.to_formula()
    norm_formula = _normalize_node(root)
    fhash = hashlib.sha256(norm_formula.encode("utf-8")).hexdigest()[:16]

    return f'''"""Auto-generated SignalEngine from ExpressionTree.

Formula: {formula_str}
Hash: {fhash}
Generated by: ExpressionTree.to_signalengine_code()
"""

import numpy as np
import pandas as pd
from typing import Dict


def _rolling_corr(a: pd.DataFrame, b: pd.DataFrame, w: int) -> pd.DataFrame:
    """Element-wise rolling Pearson correlation between two DataFrames."""
    ma = a.rolling(window=w, min_periods=max(3, w // 2)).mean()
    mb = b.rolling(window=w, min_periods=max(3, w // 2)).mean()
    cov = ((a - ma) * (b - mb)).rolling(window=w, min_periods=max(3, w // 2)).mean()
    sa = a.rolling(window=w, min_periods=max(3, w // 2)).std()
    sb = b.rolling(window=w, min_periods=max(3, w // 2)).std()
    return cov / (sa * sb)


def _rolling_cov(a: pd.DataFrame, b: pd.DataFrame, w: int) -> pd.DataFrame:
    """Element-wise rolling covariance between two DataFrames."""
    ma = a.rolling(window=w, min_periods=max(3, w // 2)).mean()
    mb = b.rolling(window=w, min_periods=max(3, w // 2)).mean()
    return ((a - ma) * (b - mb)).rolling(window=w, min_periods=max(3, w // 2)).mean()


class {class_name}:
    """SignalEngine — auto-generated from expression tree.

    Formula: {formula_str}
    Hash: {fhash}
    """

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """Generate trading signals from OHLCV data.

        Args:
            data_map: code -> DataFrame (columns: open, high, low, close, volume)

        Returns:
            code -> signal Series, value range [-1.0, 1.0]
        """
        signals = {{}}
        for code, df in data_map.items():
            if df is None or df.empty:
                signals[code] = pd.Series(dtype=float)
                continue
            try:
                factor = {factor_expr}
                # Cross-sectional rank to make values comparable across stocks
                ranked = factor.rank(pct=True)
                # Normalize to [-1, 1]
                signal = (ranked - 0.5) * 2.0
                signals[code] = signal.clip(-1.0, 1.0)
            except Exception:
                signals[code] = pd.Series(0.0, index=df.index)
        return signals
'''
