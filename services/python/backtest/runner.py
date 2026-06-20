"""Fixed backtest entrypoint: read config.json, select loader by source, import signal_engine, run engine.

Supports ``source="auto"`` to route codes to loaders by symbol format.
Supports ``interval`` for bar size (1m/5m/15m/30m/1H/4H/1D, default 1D).
Supports ``engine`` for backtest engine (daily/options, default daily).

Usage: ``python -m backtest.runner <run_dir>``
"""

import ast
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, model_validator, field_validator

# ── Data coverage helpers ────────────────────────────────────────────────
# Some free data sources (mootdx TDX server, eastmoney non-paginated, etc.)
# return data but may not cover the full requested date range.  These helpers
# detect insufficient coverage so the fallback chain can try other sources.

# A data source is considered to have "insufficient coverage" when the
# earliest bar it returns is more than this many calendar days AFTER the
# requested start_date.  e.g. with a 60-day tolerance, a source returning
# bars from 2024-01-02 for a 2020-01-01 request is flagged; one returning
# from 2023-11-15 for a 2024-01-01 request is NOT flagged.
_COVERAGE_TOLERANCE_DAYS = 60


def _data_covers_range(
    data_map: dict[str, pd.DataFrame],
    start_date: str,
    tolerance_days: int = _COVERAGE_TOLERANCE_DAYS,
) -> bool:
    """Return True if *every* DataFrame in *data_map* covers *start_date*
    within *tolerance_days*.

    An empty data_map returns False (no coverage at all).
    """
    if not data_map:
        return False
    start_ts = pd.Timestamp(start_date)
    cutoff = start_ts + pd.Timedelta(days=tolerance_days)
    for df in data_map.values():
        if df is None or df.empty:
            return False
        if df.index.min() > cutoff:
            return False
    return True

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from backtest.loaders.registry import (
    FALLBACK_CHAINS,
    LOADER_REGISTRY,
    get_loader_cls_with_fallback,
    resolve_loader,
)
from backtest.loaders.base import NoAvailableSourceError
# Symbol classification lives in ``_market_hooks`` so runner.py and
# composite.py share a single source of truth (audit-2026-05-18 B1+C1+C2).
# ``_detect_market`` is also re-exported here for back-compat with
# ``backend/src/swarm/grounding.py`` and existing tests that import it
# from ``backtest.runner``.
from backtest.engines._market_hooks import (  # noqa: F401  (re-exported)
    _detect_market,
    _detect_submarket,
    _is_china_futures,
)

logger = logging.getLogger(__name__)

_VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1H", "4H", "1D"}
_VALID_ENGINES = {"daily", "options"}
_VALID_SOURCES = {"mootdx", "eastmoney", "tencent", "baidu", "tushare", "okx", "yfinance", "akshare", "ccxt", "twelvedata", "finnhub", "futu", "coingecko", "global_indices", "commodities", "auto"}


class BacktestConfigSchema(BaseModel):
    """Validates backtest config.json before execution."""

    model_config = ConfigDict(extra="allow")

    codes: List[str]
    start_date: str
    end_date: str
    source: str = "tushare"
    interval: str = "1D"
    engine: str = "daily"
    fundamental_fields: Optional[Dict[str, List[str]]] = None

    @field_validator("codes")
    @classmethod
    def codes_not_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("codes must be a non-empty list")
        if any(not c.strip() for c in v):
            raise ValueError("codes must not contain empty strings")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        try:
            pd.Timestamp(v)
        except Exception:
            raise ValueError(f"invalid date format: {v!r} (expected YYYY-MM-DD)")
        return v

    @field_validator("interval")
    @classmethod
    def valid_interval(cls, v: str) -> str:
        if v not in _VALID_INTERVALS:
            raise ValueError(f"unsupported interval {v!r}, must be one of {_VALID_INTERVALS}")
        return v

    @field_validator("engine")
    @classmethod
    def valid_engine(cls, v: str) -> str:
        if v not in _VALID_ENGINES:
            raise ValueError(f"unsupported engine {v!r}, must be one of {_VALID_ENGINES}")
        return v

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: str) -> str:
        # Dynamically resolve valid sources from the loader registry so new
        # loaders (mootdx, eastmoney, baidu, …) are automatically accepted.
        from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
        _ensure_registered()
        valid = set(LOADER_REGISTRY.keys()) | {"auto"}
        if v not in valid:
            raise ValueError(f"unsupported source {v!r}, must be one of {sorted(valid)}")
        return v

    @field_validator("fundamental_fields")
    @classmethod
    def valid_fundamental_fields(
        cls,
        v: Optional[Dict[str, List[str]]],
    ) -> Optional[Dict[str, List[str]]]:
        if v is None:
            return v
        for table, fields in v.items():
            if not table.strip():
                raise ValueError("fundamental_fields table names must be non-empty strings")
            if any(not field.strip() for field in fields):
                raise ValueError("fundamental_fields field names must be non-empty strings")
        return v

    @model_validator(mode="after")
    def start_before_end(self) -> "BacktestConfigSchema":
        if pd.Timestamp(self.start_date) > pd.Timestamp(self.end_date):
            raise ValueError(
                f"start_date ({self.start_date}) must be <= end_date ({self.end_date})"
            )
        return self


def _load_module_from_file(file_path: Path, module_name: str):
    """Load a Python module from a file path via importlib.

    This function **must** only be called on user-supplied strategy code
    (*signal_engine.py*) that has already passed the AST sandbox validation
    performed by :func:`_validate_signal_engine_source`.  That validator blocks
    import-time executable statements (imports, function/class definitions, and
    literal constants are allowed), so executing the module is reasonably safe.
    However, the signal engine's method bodies will still run on instantiation
    inside the backtest driver — the AST sandbox does **not** inspect method
    bodies, only the top level.

    Args:
        file_path: Path to the ``.py`` file.  Must be inside an allowed run
            root (enforced by :func:`safe_run_dir` before this is called).
        module_name: Logical module name (e.g. ``"signal_engine"``).

    Returns:
        Loaded module object — typically interrogated for a ``SignalEngine``
        class.

    Security:
        - The caller **must** have already called
          :func:`_validate_signal_engine_source` on *file_path*.
        - The loaded module is inserted into ``sys.modules`` so cached imports
          elsewhere will return the same object.  This is intentional (allows
          the signal engine to import its own helpers from the run directory)
          but could be fragile if the same module name is reused across runs.
    """
    _validate_signal_engine_source(file_path)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _is_literal_node(node: ast.AST) -> bool:
    """Return ``True`` if *node* is composed entirely of literal values.

    A literal node has no side-effects at import time — it cannot execute
    code, call functions, or access attributes.  This is the foundational
    allow-list check used by the AST sandbox to decide whether a top-level
    assignment, function default argument, or annotation is safe.

    Recognized literal forms:
        - Constants (``True``, ``False``, ``None``, numbers, strings, bytes)
        - Tuples, lists, and sets whose elements are all literals
        - Dicts whose keys (if not ``None`` / dictionary unpacking) and values
          are all literals

    Args:
        node: Any AST node produced by :func:`ast.parse`.

    Returns:
        ``True`` if the subtree contains only literal values.

    Security:
        This is a **whitelist** — any node type **not** explicitly recognized
        (e.g. ``ast.Call``, ``ast.Name``, ``ast.Attribute``) returns ``False``.
        The sandbox relies on this conservative stance.
    """
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_literal_node(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _is_literal_node(key)) and _is_literal_node(value)
            for key, value in zip(node.keys, node.values)
        )
    return False


def _is_safe_constant_assignment(node: ast.AST) -> bool:
    """Return ``True`` if *node* is an assignment whose value is literal-only.

    Covers both plain (``x = 42``) and annotated (``x: int = 42`` or
    ``x: int`` without a value) assignments.  Such assignments run no code
    at import time and are therefore safe in user-supplied strategy files.

    Args:
        node: A top-level AST statement node.

    Returns:
        ``True`` for safe assignments; ``False`` for anything else (function
        calls, attribute access, comprehensions, etc.).

    Security:
        Delegates to :func:`_is_literal_node` for the value check.  An
        annotated assignment with no value (``value is None``) is always
        considered safe because it produces no runtime effect at import time.
    """
    if isinstance(node, ast.Assign):
        return _is_literal_node(node.value)
    if isinstance(node, ast.AnnAssign):
        return node.value is None or _is_literal_node(node.value)
    return False


def _is_safe_reference(node: ast.AST | None) -> bool:
    """Return ``True`` if *node* is a passive type reference with no callable side-effects.

    Used to validate function **annotations** and class **base classes** in
    user-supplied strategy code.  A safe reference can name or subscript
    types but cannot invoke functions, construct objects, or run arbitrary
    expressions.

    Allowed forms:
        - ``None`` (no annotation / base)
        - ``Name`` (e.g. ``int``, ``pd.DataFrame`` — but ``pd.DataFrame`` is
          actually an ``Attribute`` node, also allowed)
        - ``Attribute`` (e.g. ``pd.DataFrame``)
        - ``Subscript`` (e.g. ``List[int]``) — both container and index are
          recursively checked
        - ``Tuple`` (e.g. ``Tuple[int, str]``)
        - ``BinOp`` with ``|`` (PEP 604 union, e.g. ``int | None``)

    Args:
        node: An AST expression node (or ``None``) from a function annotation,
            return annotation, or class base list.

    Returns:
        ``True`` if the expression is a passive type reference.

    Security:
        This is also a **whitelist**: ``ast.Call``, ``ast.Lambda``,
        ``ast.ListComp``, ``ast.NamedExpr``, etc. are all rejected.  The
        sandbox blocks annotations like ``x: eval("__import__('os').system('ls')")``
        because ``ast.Call`` is not in the allowed set.
    """
    if node is None:
        return True
    if isinstance(node, (ast.Name, ast.Attribute, ast.Constant)):
        return True
    if isinstance(node, ast.Subscript):
        return _is_safe_reference(node.value) and _is_safe_reference(node.slice)
    if isinstance(node, ast.Tuple):
        return all(_is_safe_reference(item) for item in node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_safe_reference(node.left) and _is_safe_reference(node.right)
    return False


def _validate_function_def(node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
    """Validate a function definition node, rejecting any import-time side-effects.

    Functions (and async functions) are **allowed** in user-supplied strategy
    code, but only when their definition alone is inert.  This validator
    ensures the definition does not execute code at import time through:

    * **Decorators** — Rejected entirely.  ``@some_decorator`` calls
      ``some_decorator`` at definition time.
    * **Default arguments** — Must be literal-only (checked via
      :func:`_is_literal_node`).  ``def f(x=some_func())`` would execute
      ``some_func()`` at import time.
    * **Annotations** (parameters and return type) — Must be passive type
      references (checked via :func:`_is_safe_reference`).

    Args:
        node: An ``ast.FunctionDef`` or ``ast.AsyncFunctionDef`` node from a
            parsed strategy file.

    Raises:
        ValueError: If any decorator, non-literal default, or unsafe
            annotation is found.

    Security:
        This function inspects the function **signature only**, not the body.
        Users can write arbitrary code inside function bodies; those bodies
        only execute when the function is called (typically by the backtest
        engine), not at import time.  Validation of class-level executable
        statements inside method bodies is deferred to
        :func:`_validate_class_body`.
    """
    if node.decorator_list:
        raise ValueError(f"Decorators are not allowed on function {node.name!r}")
    for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d]]:
        if not _is_literal_node(default):
            raise ValueError(f"Non-literal default is not allowed on function {node.name!r}")
    annotations = [node.returns]
    annotations.extend(arg.annotation for arg in node.args.posonlyargs)
    annotations.extend(arg.annotation for arg in node.args.args)
    annotations.extend(arg.annotation for arg in node.args.kwonlyargs)
    annotations.append(node.args.vararg.annotation if node.args.vararg else None)
    annotations.append(node.args.kwarg.annotation if node.args.kwarg else None)
    for annotation in annotations:
        if not _is_safe_reference(annotation):
            raise ValueError(f"Unsafe annotation is not allowed on function {node.name!r}")


def _validate_class_body(node: ast.ClassDef) -> None:
    """Validate a class definition node, rejecting import-time execution.

    Class definitions are **allowed** in user-supplied strategy code, but
    their body may only contain inert statements.  This validator walks the
    class body and permits only:

    * **Docstrings** — ``ast.Expr`` wrapping an ``ast.Constant`` string.
    * **Function definitions** — Validated recursively via
      :func:`_validate_function_def`.
    * **Safe constant assignments** — Literal-only class variables checked
      via :func:`_is_safe_constant_assignment`.
    * **Pass statements** — ``pass`` or ``...``.

    Additionally enforces:
    * **No class decorators** — A decorator is executed at definition time.
    * **No unsafe base classes** — Bases must be passive type references
      (checked via :func:`_is_safe_reference`).
    * **No metaclass keywords** — ``class Foo(metaclass=...)`` is rejected.

    Args:
        node: An ``ast.ClassDef`` node from a parsed strategy file.

    Raises:
        ValueError: If any disallowed class-level statement, decorator,
            unsafe base, or keyword argument is found.

    Security:
        Every class body statement that is **not** in the explicit allow-list
        raises ``ValueError``.  This includes ``ast.Expr`` that is not a
        docstring (e.g. standalone function calls like ``print("pwned")``
        would be ``ast.Expr`` wrapping ``ast.Call`` — rejected).
    """
    if node.decorator_list:
        raise ValueError(f"Decorators are not allowed on class {node.name!r}")
    for base in node.bases:
        if not _is_safe_reference(base):
            raise ValueError(f"Unsafe base class is not allowed on class {node.name!r}")
    if node.keywords:
        raise ValueError(f"Class keywords are not allowed on class {node.name!r}")
    for child in node.body:
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _validate_function_def(child)
            continue
        if _is_safe_constant_assignment(child):
            continue
        if isinstance(child, ast.Pass):
            continue
        raise ValueError(
            f"Executable class-level statement {type(child).__name__} is not allowed"
        )


def _validate_signal_engine_source(file_path: Path) -> None:
    """AST sandbox: validate user-submitted strategy code before execution.

    This is the **primary security gate** for user-supplied *signal_engine.py*
    files.  It parses the file into an AST and rejects any top-level statement
    that could execute code at import time.  Only the following top-level
    constructs are allowed:

    * **Docstrings / string expressions** — ``ast.Expr`` wrapping an
      ``ast.Constant`` string.
    * **Import statements** — ``import`` and ``from ... import ...`` (both
      ``ast.Import`` and ``ast.ImportFrom``).
    * **Function definitions** — Validated via
      :func:`_validate_function_def` (no decorators, literal-only defaults,
      safe annotations).
    * **Class definitions** — Validated via :func:`_validate_class_body`
      (no decorators, safe bases, inert body).
    * **Safe constant assignments** — Literal-only top-level variables
      checked via :func:`_is_safe_constant_assignment`.

    Args:
        file_path: Path to the ``signal_engine.py`` file to validate.

    Raises:
        ValueError: If the file contains a ``SyntaxError``, or any
            disallowed AST node type at the top level, or any violation
            found by the recursive validators for functions/classes.

    Security:
        This is a **conservative whitelist**.  Any AST node type at the
        module body level that is **not** in the explicit allow-list raises
        ``ValueError`` and blocks loading.  Notable blocked constructs:

        * ``ast.Call`` / ``ast.Lambda`` — arbitrary function calls
        * ``ast.For`` / ``ast.While`` / ``ast.With`` / ``ast.Try`` — loops
          and context managers
        * ``ast.If`` / ``ast.Match`` — conditional execution
        * ``ast.Delete`` / ``ast.Raise`` / ``ast.Assert`` / ``ast.Global`` /
          ``ast.Nonlocal`` — side-effecting statements
        * ``ast.AugAssign`` / ``ast.AnnAssign`` with a callable value —
          assignments that run code

        **Known limitation**: method bodies are not inspected.  The sandbox
        allows arbitrary code inside function/method bodies because those
        bodies only execute when the function is called.  The signal engine's
        methods are called by the backtest driver, which is trusted context.
    """
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except SyntaxError as exc:
        raise ValueError(f"Invalid signal_engine.py syntax: {exc}") from exc

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _validate_function_def(node)
            continue
        if isinstance(node, ast.ClassDef):
            _validate_class_body(node)
            continue
        if _is_safe_constant_assignment(node):
            continue
        raise ValueError(
            f"Executable top-level statement {type(node).__name__} is not allowed"
        )


# --- Market detection ---
# ``_MARKET_PATTERNS``, ``_detect_market``, ``_is_china_futures``,
# ``_detect_submarket`` are imported from ``_market_hooks`` above and
# re-exported here for back-compat (swarm/grounding.py, tests).

# Back-compat: market type -> legacy source name (for engine selection & metrics)
_MARKET_TO_SOURCE = {
    "a_share": "mootdx",
    "us_equity": "yfinance",
    "hk_equity": "yfinance",
    "crypto": "okx",
    "futures": "mootdx",
    "fund": "mootdx",
    "macro": "akshare",
    "forex": "akshare",
}


def _detect_source(code: str) -> str:
    """Infer legacy source name from a symbol for back-compat with metrics/engine selection.

    Looks up the detected market type in ``_MARKET_TO_SOURCE`` to map
    market categories to traditional source names.  This is used by older
    code paths (e.g. annualization, engine hints) that still reason in
    terms of sources rather than market types.

    Args:
        code: Ticker / symbol string (e.g. ``"000001.SZ"``, ``"AAPL"``,
            ``"BTC-USDT"``).

    Returns:
        Legacy source name (``"mootdx"``, ``"yfinance"``, ``"okx"``,
        ``"ccxt"``, ``"akshare"``, etc.).  Defaults to ``"mootdx"`` for
        unrecognized market types.
    """
    market = _detect_market(code)
    return _MARKET_TO_SOURCE.get(market, "mootdx")


def _group_codes_by_market(codes: List[str]) -> Dict[str, List[str]]:
    """Group symbols by detected market type for per-market data fetching.

    Each code is classified via :func:`_detect_market` (which uses the
    regex patterns from ``_market_hooks``).  Codes with the same market
    type are batched together so they can be fetched from the same loader.

    Args:
        codes: List of symbol strings (mixed markets allowed).

    Returns:
        ``{market_type: [code, ...]}`` mapping.  Market types include
        ``"a_share"``, ``"us_equity"``, ``"hk_equity"``, ``"crypto"``,
        ``"futures"``, ``"forex"``, ``"fund"``, ``"macro"``, ``"index"``,
        and ``"commodity"``.
    """
    groups: Dict[str, List[str]] = {}
    for code in codes:
        market = _detect_market(code)
        groups.setdefault(market, []).append(code)
    return groups


def _group_codes_by_source(codes: List[str]) -> Dict[str, List[str]]:
    """Group symbols by inferred legacy source name for back-compat reporting.

    Delegates to :func:`_detect_source` per symbol, which maps market type
    to legacy source name via ``_MARKET_TO_SOURCE``.  Used by the run card
    to report which effective sources were used in auto mode.

    Args:
        codes: List of symbol strings.

    Returns:
        ``{source_name: [code, ...]}`` mapping.  Source names are legacy
        identifiers like ``"mootdx"``, ``"yfinance"``, ``"okx"``, etc.
    """
    groups: Dict[str, List[str]] = {}
    for code in codes:
        src = _detect_source(code)
        groups.setdefault(src, []).append(code)
    return groups


def _get_loader(source: str):
    """Return a DataLoader **class** for a source name, with automatic fallback.

    Uses ``get_loader_cls_with_fallback`` to walk the source's fallback
    chain and return the first available loader.  If the chain is exhausted,
    falls back to ``tushare`` as a last resort (when registered).

    Args:
        source: Source name (``"mootdx"``, ``"eastmoney"``, ``"tencent"``,
            ``"baidu"``, ``"tushare"``, ``"yfinance"``, ``"akshare"``,
            ``"okx"``, ``"ccxt"``, ``"twelvedata"``, ``"finnhub"``,
            ``"futu"``, ``"coingecko"``, etc.).

    Returns:
        A **DataLoader class** (not an instance).  The caller is expected
        to instantiate it.

    Raises:
        NoAvailableSourceError: If no source in the chain is available and
            ``tushare`` is not registered.
    """
    try:
        return get_loader_cls_with_fallback(source)
    except NoAvailableSourceError:
        # Ultimate fallback for unknown sources
        if "tushare" in LOADER_REGISTRY:
            return LOADER_REGISTRY["tushare"]
        raise


def _normalize_codes(codes: List[str], source: str) -> List[str]:
    """Normalize symbol strings for a specific data source's API format.

    Most sources accept codes as-is, but crypto exchanges (OKX, CCXT)
    expect dash-separated pairs (``"BTC-USDT"``) rather than slash-separated
    (``"BTC/USDT"``).  This function applies the appropriate transformation.

    Args:
        codes: Raw code list as entered by the user.
        source: Data source name.

    Returns:
        Normalized codes.  For ``okx`` / ``ccxt``: slashes replaced with
        dashes and uppercased.  For all other sources: returned unchanged.
    """
    if source in ("okx", "ccxt"):
        return [c.replace("/", "-").upper() for c in codes]
    return codes


# --- Main entry ---

def main(run_dir: Path) -> None:
    """Load config, fetch data, run the selected backtest engine.

    With ``source="auto"``, routes each code through the appropriate loader.

    Args:
        run_dir: Run directory containing ``config.json`` and ``code/signal_engine.py``.
            The path is validated against the allowed run roots
            (``ASTOCKPURSUE_ALLOWED_RUN_ROOTS`` plus the defaults) before any
            file is read so an arbitrary filesystem location cannot be used
            to source ``code/signal_engine.py``.
    """
    # Guard the CLI entry point with the same root whitelist the MCP
    # ``backtest`` tool already uses (src/tools/backtest_tool.py:23). Without
    # this, ``python -m backtest.runner /tmp/attacker_path`` would happily
    # import ``signal_engine.py`` from anywhere on disk; the AST scrubber
    # below blocks executable top-level statements but a method body still
    # runs on instantiation. See ``safe_run_dir`` for the policy.
    from src.tools.path_utils import safe_run_dir
    try:
        run_dir = safe_run_dir(str(run_dir))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    config_path = run_dir / "config.json"
    if not config_path.exists():
        print(json.dumps({"error": "config.json not found"}))
        sys.exit(1)

    raw_config = json.loads(config_path.read_text(encoding="utf-8"))

    # Validate config schema
    try:
        BacktestConfigSchema(**raw_config)
    except Exception as exc:
        errors = str(exc)
        print(json.dumps({"error": f"Invalid config: {errors}"}))
        sys.exit(1)

    config = raw_config
    source = config.get("source", "tushare")
    codes = config.get("codes", [])

    # Load signal engine
    signal_path = run_dir / "code" / "signal_engine.py"
    if not signal_path.exists():
        print(json.dumps({"error": "code/signal_engine.py not found"}))
        sys.exit(1)

    signal_module = _load_module_from_file(signal_path, "signal_engine")
    engine_cls = getattr(signal_module, "SignalEngine", None)
    if engine_cls is None:
        print(json.dumps({"error": "SignalEngine class not found in signal_engine.py"}))
        sys.exit(1)

    # Data: auto split vs single loader
    interval = config.get("interval", "1D")

    if source == "auto":
        data_map = _fetch_auto(codes, config, interval)
    else:
        codes = _normalize_codes(codes, source)
        config["codes"] = codes
        LoaderCls = _get_loader(source)
        loader = LoaderCls()
        data_map = loader.fetch(
            codes,
            config.get("start_date", ""),
            config.get("end_date", ""),
            fields=config.get("extra_fields") or None,
            interval=interval,
        )
        # Runtime fallback: try next sources in chain when primary returns
        # empty OR when the returned data doesn't cover the requested start_date.
        # This is critical for free sources like mootdx whose TDX servers may
        # only keep ~2-3 years of daily bars — they return data successfully
        # but the range is too short for longer backtests.
        start_date = config.get("start_date", "")
        needs_fallback = (
            not _data_covers_range(data_map, start_date)
            if data_map and start_date
            else not data_map
        )
        if needs_fallback and codes:
            market = _detect_market(codes[0])
            for fb_name in FALLBACK_CHAINS.get(market, []):
                if fb_name == source or fb_name not in LOADER_REGISTRY:
                    continue
                try:
                    fb_loader = LOADER_REGISTRY[fb_name]()
                except Exception:
                    continue
                if not fb_loader.is_available():
                    continue
                fb_codes = _normalize_codes(codes, fb_name)
                fb_data_map = fb_loader.fetch(
                    fb_codes, config.get("start_date", ""),
                    config.get("end_date", ""), interval=interval,
                )
                if fb_data_map and _data_covers_range(fb_data_map, start_date):
                    logger.info("Runtime fallback: %s -> %s (better coverage)", source, fb_name)
                    data_map = fb_data_map
                    source = fb_name
                    loader = fb_loader
                    break
                elif fb_data_map:
                    # Secondary source also has insufficient range, but it's
                    # better than nothing — use it if primary was completely empty.
                    if not data_map:
                        logger.info("Runtime fallback: %s -> %s (partial coverage)", source, fb_name)
                        data_map = fb_data_map
                        source = fb_name
                        loader = fb_loader
                        break
    # Survivorship-bias check: codes that returned empty DataFrames
    missing_codes = [c for c in codes if c not in data_map or len(data_map.get(c, [])) == 0]
    if missing_codes:
        msg = f"{len(missing_codes)} symbol(s) have no data (delisted / inactive / wrong code): {', '.join(missing_codes[:5])}{'...' if len(missing_codes) > 5 else ''}"
        logger.warning("Survivorship bias: %s", msg)
        config.setdefault("_warnings", []).append(msg)
        # Remove missing codes so engine doesn't crash
        codes = [c for c in codes if c not in missing_codes]
        config["codes"] = codes
        data_map = {k: v for k, v in data_map.items() if k not in missing_codes}

    if not data_map:
        print(json.dumps({"error": "No data fetched — all symbols returned empty"}))
        sys.exit(1)

    if source == "auto":
        config["_run_card_effective_sources"] = sorted(_group_codes_by_source(codes))
    else:
        config["_run_card_effective_sources"] = [source]

    # Engine
    engine_type = config.get("engine", "daily")
    signal_engine = engine_cls()

    # Annualization bars
    effective_source = _detect_primary_source(codes, source)
    from backtest.metrics import calc_bars_per_year
    # Cross-market: use calendar-day annualization (bars_per_year=None)
    market_types = {_detect_market(c) for c in codes}
    if len(market_types) > 1:
        bars_per_year = None
    else:
        bars_per_year = calc_bars_per_year(interval, effective_source)

    # Auto mode: wrap preloaded data in a dummy loader
    if source == "auto":
        loader = _AutoLoader(data_map)

    if engine_type == "options":
        from backtest.engines.options_portfolio import run_options_backtest
        run_options_backtest(config, loader, signal_engine, run_dir, bars_per_year=bars_per_year)
    else:
        market_engine = _create_market_engine(effective_source, config, codes)
        from src.trading.backtest_driver import BacktestDriver
        driver = BacktestDriver()
        driver.run(config, loader, signal_engine, run_dir, market_engine, bars_per_year=bars_per_year)


def _create_market_engine(source: str, config: dict, codes: List[str]):
    """Create the appropriate market engine based on **market type**.

    This function routes a set of symbols to the correct trading engine by
    classifying each code's market (A-share, US equity, crypto, futures,
    forex, fund, macro, etc.) and picking the corresponding engine class.

    **Routing priority (first match wins):**

    1. **Cross-market** — Multiple market types detected →
       ``CompositeEngine`` (delegates per-market).
    2. **Futures** — ``ChinaFuturesEngine`` for Chinese futures symbols,
       ``GlobalFuturesEngine`` otherwise.
    3. **Forex** — ``ForexEngine``.
    4. **A-share** — ``ChinaAEngine`` (covers all A-share loaders:
       mootdx, tushare, eastmoney, tencent, futu, baidu, twelvedata, akshare).
    5. **Crypto** — ``CryptoEngine`` (detected from symbol patterns, not
       source name).
    6. **US/HK equity** — ``GlobalEquityEngine`` (sub-market parameter set
       via ``_detect_submarket``).
    7. **Fund / Macro** — ``ChinaAEngine`` (Chinese fund/macro indices).
    8. **Index / Commodity** — ``GlobalEquityEngine`` with ``market="us"``.
    9. **Fallback** — If the source name is ``"okx"`` or ``"ccxt"`` →
       ``CryptoEngine``.  Otherwise defaults to ``ChinaAEngine`` (the
       safest assumption for the predominantly Chinese user base).

    Args:
        source: Effective source name (may be the config value or the
            auto-detected primary source from :func:`_detect_primary_source`).
        config: Backtest config dict (passed through to the engine constructor).
        codes: All symbols for this backtest run.

    Returns:
        An engine instance (``ChinaAEngine``, ``CryptoEngine``,
        ``GlobalEquityEngine``, ``CompositeEngine``, ``ChinaFuturesEngine``,
        ``GlobalFuturesEngine``, or ``ForexEngine``).

    Note:
        The *source* name is only used as a hint in steps 2 and 9
        (distinguishing China vs global futures, and crypto source-name
        fallback).  All other routing is market-driven, so new A-share
        loaders work without modifying this function.
    """
    # Detect dominant market type from codes
    markets = {_detect_market(c) for c in codes} if codes else set()

    # Cross-market -> CompositeEngine
    if len(markets) > 1:
        from backtest.engines.composite import CompositeEngine
        return CompositeEngine(config, codes)

    # Futures routing
    if "futures" in markets:
        if any(_is_china_futures(c) for c in codes):
            from backtest.engines.china_futures import ChinaFuturesEngine
            return ChinaFuturesEngine(config)
        from backtest.engines.global_futures import GlobalFuturesEngine
        return GlobalFuturesEngine(config)

    # Forex routing
    if "forex" in markets:
        from backtest.engines.forex import ForexEngine
        return ForexEngine(config)

    # ── Market-driven routing (source name is secondary) ─────────────────

    # A-share market → ChinaAEngine (covers ALL A-share loaders)
    if "a_share" in markets:
        from backtest.engines.china_a import ChinaAEngine
        return ChinaAEngine(config)

    # Crypto market → CryptoEngine
    if "crypto" in markets:
        from backtest.engines.crypto import CryptoEngine
        return CryptoEngine(config)

    # US/HK equity → GlobalEquityEngine
    if markets & {"us_equity", "hk_equity"}:
        from backtest.engines.global_equity import GlobalEquityEngine
        market = _detect_submarket(codes)
        return GlobalEquityEngine(config, market=market)

    # Fund / macro / index / commodity → ChinaAEngine as safe default for
    # Chinese markets; GlobalEquityEngine for global ones.
    if markets & {"fund", "macro"}:
        from backtest.engines.china_a import ChinaAEngine
        return ChinaAEngine(config)
    if markets & {"index", "commodity"}:
        from backtest.engines.global_equity import GlobalEquityEngine
        return GlobalEquityEngine(config, market="us")

    # ── Fallback: source-name hint for unknown/unclassified codes ─────────
    if source in ("okx", "ccxt"):
        from backtest.engines.crypto import CryptoEngine
        return CryptoEngine(config)

    # Default: assume A-share (safest for Chinese users)
    from backtest.engines.china_a import ChinaAEngine
    return ChinaAEngine(config)


def _detect_primary_source(codes: List[str], source: str) -> str:
    """Pick the dominant data source for annualization calculations.

    When ``source="auto"``, different symbols may use different loaders
    (e.g. A-shares via mootdx, crypto via okx).  This function identifies
    the source covering the most symbols so that metrics like bars-per-year
    can use appropriate trading-calendar assumptions.

    Args:
        codes: All symbols for the backtest.
        source: Config ``source`` field.  If not ``"auto"``, it is returned
            unchanged.

    Returns:
        Dominant source name.  In single-source mode this is just *source*.
        In auto mode with mixed sources, the source with the most symbols
        wins (ties broken by ``max`` iteration order).
    """
    if source != "auto":
        return source
    groups = _group_codes_by_source(codes)
    if len(groups) == 1:
        return list(groups.keys())[0]
    # Mixed: use the source with the most symbols
    return max(groups, key=lambda s: len(groups[s]))


def _fetch_auto(codes: List[str], config: dict, interval: str = "1D") -> dict:
    """Auto mode: route each market group through its optimal data source chain.

    When ``source="auto"`` in the backtest config, each symbol is classified
    by market type (A-share, US equity, crypto, futures, etc.) and routed
    through the appropriate loader with fallback.  This avoids the need to
    manually split symbols by source.

    **Pipeline per market group:**

    1. **PG cache check** — Each code is looked up in PostgreSQL cache.
       Codes with at least 5 cached bars skip fetching entirely.
    2. **Loader resolution** — ``resolve_loader(market)`` picks the best
       available source for the market type.  Falls back to a legacy source
       (via ``_MARKET_TO_SOURCE``) if the chain is exhausted.
    3. **Concurrent fetch** — All uncached codes for a market are fetched
       in parallel via ``fetch_concurrent``.
    4. **Runtime fallback** — If the primary source returns empty or does
       not cover the requested ``start_date`` (checked via
       :func:`_data_covers_range`), remaining sources in the market's fallback
       chain are tried in order.
    5. **Cache write-back** — Fetched data is written to both PG cache
       and Parquet cold storage for future runs.
    6. **Coverage warning** — If even the best source does not cover
       ``start_date``, a warning is appended to ``config["_warnings"]``.

    Args:
        codes: All symbols from the backtest config.
        config: Backtest config dict (mutated in-place: ``_warnings`` may be
            appended and ``_run_card_effective_sources`` is set by the caller).
        interval: Bar interval string (``"1D"``, ``"1H"``, etc.).

    Returns:
        ``{code: DataFrame}`` map covering all symbols that could be fetched.
        Symbols that failed across all sources are silently omitted; the
        caller (:func:`main`) handles survivorship-bias reporting.

    Note:
        This function mutates *config* in-place: it appends coverage-gap
        warnings to ``config["_warnings"]``.  The caller is responsible for
        setting ``config["_run_card_effective_sources"]`` afterward.
    """
    from backtest.loaders.base import fetch_concurrent

    # ── Cache support ─────────────────────────────────────────────────
    try:
        from backtest.loaders.cache import query_cache, write_cache
        _cache_ok = True
    except Exception:
        _cache_ok = False

    market_groups = _group_codes_by_market(codes)
    merged = {}
    start_date = config.get("start_date", "")
    end_date = config.get("end_date", "")

    for market, market_codes in market_groups.items():
        # ── Check PG cache first for each code ─────────────────────────
        uncached_codes: list[str] = []
        if _cache_ok:
            for code in market_codes:
                cached = query_cache(code, interval, start_date, end_date)
                if cached is not None and len(cached) >= 5:
                    merged[code] = cached
                else:
                    uncached_codes.append(code)
        else:
            uncached_codes = list(market_codes)

        if not uncached_codes:
            continue

        # ── Resolve loader ─────────────────────────────────────────────
        try:
            loader = resolve_loader(market)
        except NoAvailableSourceError as exc:
            legacy_src = _MARKET_TO_SOURCE.get(market, "mootdx")
            logger.warning("Fallback chain failed for %s: %s — trying %s", market, exc, legacy_src)
            try:
                LoaderCls = _get_loader(legacy_src)
                loader = LoaderCls()
            except Exception as e2:
                logger.warning("Legacy fallback also failed for %s: %s — skipping", market, e2)
                continue

        src_name = getattr(loader, "name", "unknown")
        normalized_codes = _normalize_codes(uncached_codes, src_name)
        fields = config.get("extra_fields") if src_name == "tushare" else None

        # ── Fetch — concurrent for multiple codes ──────────────────────
        result = fetch_concurrent(
            loader, normalized_codes, start_date, end_date,
            interval=interval, fields=fields,
        )

        # Runtime fallback: try remaining sources when primary returns empty
        # OR when the returned data doesn't cover the requested start_date.
        needs_fb = (
            not _data_covers_range(result, start_date)
            if result and start_date
            else not result
        )
        if needs_fb:
            for fb_name in FALLBACK_CHAINS.get(market, []):
                if fb_name == src_name or fb_name not in LOADER_REGISTRY:
                    continue
                try:
                    fb_loader = LOADER_REGISTRY[fb_name]()
                except Exception:
                    continue
                if not fb_loader.is_available():
                    continue
                fb_codes = _normalize_codes(uncached_codes, fb_name)
                fb_result = fetch_concurrent(
                    fb_loader, fb_codes, start_date, end_date,
                    interval=interval,
                )
                if fb_result and _data_covers_range(fb_result, start_date):
                    logger.info("Runtime fallback: %s -> %s for %s (better coverage)", src_name, fb_name, market)
                    result = fb_result
                    break
                elif fb_result:
                    # Partial coverage — use if primary was completely empty.
                    if not result:
                        logger.info("Runtime fallback: %s -> %s for %s (partial coverage)", src_name, fb_name, market)
                        result = fb_result
                        break

        # ── Write back to cache + Parquet store ────────────────────────
        if _cache_ok:
            for code, df in result.items():
                try:
                    write_cache(code, interval, df)
                except Exception:
                    pass
        # Also write to Parquet store for cold storage
        try:
            from backtest.loaders.store import update_store
            for code, df in result.items():
                try:
                    update_store(code, interval, df)
                except Exception:
                    pass
        except Exception:
            pass

        # Warn if even the best source doesn't cover the requested range.
        if result and start_date and not _data_covers_range(result, start_date):
            for code, df in result.items():
                if df is not None and not df.empty:
                    logger.warning(
                        "Data coverage gap: requested start=%s, earliest bar for %s is %s. "
                        "The free data source may not retain history this far back. "
                        "Try tushare (with token), akshare, or twelvedata for longer histories.",
                        start_date, code, df.index.min().strftime("%Y-%m-%d"),
                    )
                    break
            config.setdefault("_warnings", []).append(
                f"Insufficient data coverage: requested start_date={start_date}, "
                f"but the earliest available bar is after that. "
                f"The backtest will run on the available range only."
            )

        merged.update(result)

    return merged


class _AutoLoader:
    """Dummy loader for auto mode: returns pre-fetched data maps."""

    def __init__(self, data_map: dict):
        """Initialize with a pre-built code-to-DataFrame mapping.

        Args:
            data_map: ``{code: DataFrame}`` mapping produced by
                :func:`_fetch_auto`.  Stored by reference (no copy).
        """
        self._data = data_map

    def fetch(self, codes, start_date, end_date, fields=None, interval="1D"):
        """Return preloaded rows for requested codes."""
        return {c: df for c, df in self._data.items() if c in codes}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backtest.runner <run_dir>")
        sys.exit(1)
    main(Path(sys.argv[1]))
