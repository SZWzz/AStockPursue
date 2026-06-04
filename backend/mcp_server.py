#!/usr/bin/env python3
"""AStockPursue MCP Server — expose 22 finance research tools to any MCP client.

Works with OpenClaw, Claude Desktop, Cursor, and any MCP-compatible client.
Zero API key required for HK/US/crypto markets (yfinance, OKX, AKShare are free).

Usage:
    python mcp_server.py                    # stdio transport (default)
    python mcp_server.py --transport sse    # SSE transport for web clients

OpenClaw config (~/.openclaw/config.yaml):
    skills:
      - name: AStockPursue
        command: python /path/to/backend/mcp_server.py

Claude Desktop config:
    {
      "mcpServers": {
        "AStockPursue": {
          "command": "python",
          "args": ["/path/to/backend/mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

# Ensure backend/ is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastmcp import FastMCP

mcp = FastMCP("AStockPursue")

logger = logging.getLogger(__name__)

_data_tokens_loaded = False


def _ensure_data_tokens() -> None:
    """Load data-source tokens from .env + DB so loaders can find them."""
    global _data_tokens_loaded
    if _data_tokens_loaded:
        return
    _data_tokens_loaded = True
    try:
        from src.providers.llm import _ensure_dotenv
        _ensure_dotenv()
    except Exception:
        pass
    try:
        from src.auth.user_config import load_user_config
        load_user_config(1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Lazy-loaded singletons
# ---------------------------------------------------------------------------

_skills_loader = None
_registry = None
_include_shell_tools = True


def _env_shell_tools_enabled() -> bool:
    """Return whether shell tools were explicitly enabled for network MCP."""
    return os.getenv("ASTOCKPURSUE_ENABLE_SHELL_TOOLS", "").strip().lower() in {"1", "true", "yes", "on"}


def _get_skills_loader():
    global _skills_loader
    if _skills_loader is None:
        from src.agent.skills import SkillsLoader

        _skills_loader = SkillsLoader()
    return _skills_loader


def _get_registry():
    global _registry
    if _registry is None:
        from src.tools import build_registry

        _registry = build_registry(include_shell_tools=_include_shell_tools)
    return _registry


# ---------------------------------------------------------------------------
# Skill tools
# ---------------------------------------------------------------------------


@mcp.tool
def list_skills() -> str:
    """List all available finance skills with names and descriptions.

    Returns a JSON array of {name, description} for all loaded skills.
    Use load_skill(name) to get the full documentation for any skill.
    """
    loader = _get_skills_loader()
    skills = [{"name": s.name, "description": s.description} for s in loader.skills]
    return json.dumps(skills, ensure_ascii=False, indent=2)


@mcp.tool
def load_skill(name: str) -> str:
    """Load full documentation for a named finance skill.

    Each skill is a comprehensive knowledge document covering methodology,
    code templates, parameters, and examples. Use list_skills() first to
    discover available skills.

    Args:
        name: Skill name (e.g. 'strategy-generate', 'risk-analysis', 'technical-basic').
    """
    loader = _get_skills_loader()
    content = loader.get_content(name)
    if content.startswith("Error:"):
        return json.dumps({"status": "error", "error": content}, ensure_ascii=False)
    return json.dumps({"status": "ok", "skill": name, "content": content}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Backtest tool
# ---------------------------------------------------------------------------


@mcp.tool
def backtest(run_dir: str) -> str:
    """Run a vectorized backtest using config.json and code/signal_engine.py.

    The run_dir must contain:
    - config.json: backtest configuration (source, codes, dates, etc.)
    - code/signal_engine.py: strategy signal generation code

    Supported data sources (set in config.json "source" field):
    - "mootdx": China A-shares via TDX TCP (free, fastest, no API key) — RECOMMENDED for A-shares
    - "eastmoney": China A-shares via HTTP K-line (free, stable, no API key)
    - "tencent": China A-shares, HK stocks (free, real-time, no API key)
    - "baidu": China A-shares (free, K-line with MA, no API key)
    - "tushare": China A-shares, funds, futures, macro (requires TUSHARE_TOKEN)
    - "yfinance": US stocks, HK stocks, ETFs, indices (free)
    - "akshare": A-shares, US, HK, futures, forex, macro (free)
    - "okx": cryptocurrency (free, no API key needed)
    - "ccxt": crypto from 100+ exchanges (free, no API key)
    - "twelvedata": global all-markets (requires TWELVE_DATA_API_KEY)
    - "finnhub": US stocks (requires FINNHUB_API_KEY)
    - "futu": A-shares, HK stocks (requires FutuOpenD running locally)
    - "coingecko": crypto market cap & trending (free, no API key)
    - "global_indices": global stock indices via yfinance (free)
    - "commodities": metals, energy, agricultural via yfinance (free)
    - "auto": auto-detect based on symbol format with market-level fallback chains

    The auto source routes A-shares through: mootdx → tushare → eastmoney → tencent → futu → baidu → twelvedata → akshare.

    Returns metrics (Sharpe, return, drawdown, etc.) and artifact paths.

    Args:
        run_dir: Path to the run directory containing config.json and code/.
    """
    _ensure_data_tokens()
    from src.tools.backtest_tool import run_backtest

    return run_backtest(run_dir)


# ---------------------------------------------------------------------------
# Factor analysis tool
# ---------------------------------------------------------------------------


@mcp.tool
def factor_analysis(
    codes: list[str],
    factor_name: str,
    start_date: str,
    end_date: str,
    source: str = "auto",
    top_n: int = 10,
    bottom_n: int = 10,
) -> str:
    """Compute factor IC/IR analysis and layered backtest for a cross-section of stocks.

    Analyzes factor predictive power using Spearman rank IC, IR (IC/std),
    and top/bottom quintile return spreads.

    Args:
        codes: List of stock codes (e.g. ["000001.SZ", "600519.SH"]).
        factor_name: Factor column name in daily_basic data (e.g. "pe_ttm", "pb", "turnover_rate").
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        source: Data source ("mootdx", "tushare", "yfinance", "akshare", "auto").
        top_n: Number of top-ranked stocks per period.
        bottom_n: Number of bottom-ranked stocks per period.
    """
    registry = _get_registry()
    return registry.execute(
        "factor_analysis",
        {
            "codes": codes,
            "factor_name": factor_name,
            "start_date": start_date,
            "end_date": end_date,
            "source": source,
            "top_n": top_n,
            "bottom_n": bottom_n,
        },
    )


# ---------------------------------------------------------------------------
# Options pricing tool
# ---------------------------------------------------------------------------


@mcp.tool
def analyze_options(
    spot: float,
    strike: float,
    expiry_days: int,
    risk_free_rate: float = 0.03,
    volatility: float = 0.25,
    option_type: str = "call",
) -> str:
    """Calculate Black-Scholes option price and Greeks (Delta, Gamma, Theta, Vega).

    Args:
        spot: Current underlying price.
        strike: Strike price.
        expiry_days: Days until expiration.
        risk_free_rate: Annual risk-free rate (default 0.03 = 3%).
        volatility: Annual volatility (default 0.25 = 25%).
        option_type: "call" or "put".
    """
    registry = _get_registry()
    return registry.execute(
        "options_pricing",
        {
            "spot": spot,
            "strike": strike,
            "expiry_days": expiry_days,
            "risk_free_rate": risk_free_rate,
            "volatility": volatility,
            "option_type": option_type,
        },
    )


# ---------------------------------------------------------------------------
# Pattern recognition tool
# ---------------------------------------------------------------------------


@mcp.tool
def pattern_recognition(run_dir: str) -> str:
    """Detect technical chart patterns (head-and-shoulders, double top/bottom,
    triangles, wedges, channels) in OHLCV data.

    Reads price data from run_dir/artifacts/ohlcv_*.csv files.
    Can be called before coding (to inform strategy) or after backtest (to analyse).

    Args:
        run_dir: Path to run directory containing artifacts/ohlcv_*.csv.
    """
    registry = _get_registry()
    return registry.execute("pattern", {"run_dir": run_dir})


# ---------------------------------------------------------------------------
# Web & document reading tools
# ---------------------------------------------------------------------------


@mcp.tool
def read_url(url: str) -> str:
    """Fetch a web page and convert it to clean Markdown text.

    Strips ads, navigation, and styling. Useful for reading API docs,
    financial articles, research reports, and GitHub READMEs.

    Args:
        url: Target URL to read.
    """
    from src.tools.web_reader_tool import read_url as _read_url

    return _read_url(url)


@mcp.tool
def read_document(file_path: str) -> str:
    """Extract text from a PDF document with OCR fallback for scanned pages.

    Supports text-based and image-based PDFs. Automatically uses OCR
    for pages with insufficient extractable text.

    Args:
        file_path: Absolute path to the PDF file.
    """
    registry = _get_registry()
    return registry.execute("read_document", {"file_path": file_path})


# ---------------------------------------------------------------------------
# Web search tool
# ---------------------------------------------------------------------------


@mcp.tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo and return top results.

    Returns titles, URLs, and snippets. Use read_url() to fetch full content
    from any result URL. Free, no API key required.

    Args:
        query: Search query string.
        max_results: Maximum results to return (default 5, max 10).
    """
    registry = _get_registry()
    return registry.execute(
        "web_search",
        {
            "query": query,
            "max_results": min(max_results, 10),
        },
    )


# ---------------------------------------------------------------------------
# File I/O tools (sandboxed to workspace)
# ---------------------------------------------------------------------------


def _mcp_workspace() -> str:
    """Return the default MCP workspace directory, creating it if needed."""
    p = Path.home() / ".AStockPursue" / "workspace"
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


@mcp.tool
def write_file(path: str, content: str, run_dir: str = "") -> str:
    """Write content to a file in a sandboxed workspace.

    Args:
        path: File path relative to run_dir.
        content: File content to write.
        run_dir: Workspace root directory. Defaults to ~/.AStockPursue/workspace/.
    """
    registry = _get_registry()
    return registry.execute("write_file", {
        "path": path,
        "content": content,
        "run_dir": run_dir or _mcp_workspace(),
    })


@mcp.tool
def read_file(path: str, run_dir: str = "") -> str:
    """Read the contents of a file from a sandboxed workspace.

    Args:
        path: File path to read.
        run_dir: Workspace root directory. Defaults to ~/.AStockPursue/workspace/.
    """
    registry = _get_registry()
    return registry.execute("read_file", {
        "path": path,
        "run_dir": run_dir or _mcp_workspace(),
    })


# ---------------------------------------------------------------------------
# Swarm team tool
# ---------------------------------------------------------------------------


@mcp.tool
def list_swarm_presets() -> str:
    """List available swarm multi-agent team presets.

    Each preset defines a team of specialized agents (e.g. investment committee,
    quant desk, risk committee) that collaborate on complex research tasks.
    Returns preset names, descriptions, agent counts, and required variables.
    """
    from src.swarm.presets import list_presets

    presets = list_presets()
    return json.dumps(presets, ensure_ascii=False, indent=2)


@mcp.tool
def run_swarm(preset_name: str, variables: dict[str, str]) -> str:
    """Start a swarm multi-agent team and return immediately with the run_id.

    Assembles a team of specialized agents that collaborate through a DAG workflow
    in a background thread. For example, the 'investment_committee' preset runs
    bull analyst, bear analyst, risk officer, and portfolio manager in sequence.

    Use list_swarm_presets() to see available presets and their required variables.
    Use get_swarm_status(run_id) to poll for progress.
    Use get_run_result(run_id) to fetch the final report once completed.

    Args:
        preset_name: Swarm preset name (e.g. 'investment_committee', 'quant_strategy_desk').
        variables: Required variables for the preset (e.g. {"target": "AAPL.US", "market": "US"}).
    """
    from src.swarm.runtime import SwarmRuntime
    from src.swarm.store import SwarmStore, swarm_runs_root

    swarm_dir = swarm_runs_root()
    store = SwarmStore(base_dir=swarm_dir)
    runtime = SwarmRuntime(store=store)

    try:
        run = runtime.start_run(
            preset_name, variables, include_shell_tools=_include_shell_tools
        )
    except FileNotFoundError as exc:
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
    except ValueError as exc:
        return json.dumps({"status": "error", "error": f"DAG validation failed: {exc}"}, ensure_ascii=False)

    return json.dumps(
        {
            "status": "started",
            "preset": preset_name,
            "run_id": run.id,
            "hint": "Use get_swarm_status(run_id) to check progress, get_run_result(run_id) for the final report.",
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Market data tool
# ---------------------------------------------------------------------------

DEFAULT_MAX_ROWS = 250

_SOURCE_PATTERNS = [
    (re.compile(r"^\d{6}\.(SZ|SH|BJ)$", re.I), "mootdx"),  # A-shares: mootdx is free, fastest, no auth
    (re.compile(r"^[A-Z]+\.US$", re.I), "yfinance"),
    (re.compile(r"^\d{3,5}\.HK$", re.I), "yfinance"),
    (re.compile(r"^[A-Z]+-USDT$", re.I), "okx"),
    (re.compile(r"^[A-Z]+/USDT$", re.I), "ccxt"),
]


def _detect_source(code: str) -> str:
    for pattern, source in _SOURCE_PATTERNS:
        if pattern.match(code):
            return source
    return "mootdx"


def _get_loader(source: str):
    """Get loader class via registry with fallback support."""
    from backtest.loaders.registry import get_loader_cls_with_fallback

    return get_loader_cls_with_fallback(source)


def _cap_rows(records: list, max_rows: int) -> list | dict[str, object]:
    """Bound a per-symbol row list to keep the MCP payload within budget.

    max_rows==0 disables the cap (full list, unchanged shape). A negative
    max_rows is invalid and enforces the default cap (never unbounded).
    Otherwise an oversized symbol is *evenly strided* — every step-th bar,
    with the last bar pinned — so the returned series spans the full range
    (no head+tail gap, no synthetic ``_gap`` sentinel). Symbols within the
    cap are returned unchanged (plain list) — small queries are
    byte-identical.
    """
    n = len(records)
    if max_rows < 0:
        max_rows = DEFAULT_MAX_ROWS  # negative invalid -> enforce cap, never unbounded
    if max_rows == 0 or n <= max_rows:
        return records
    step = math.ceil(n / max_rows)
    sampled = records[::step]
    if sampled[-1] is not records[-1]:
        sampled = sampled + [records[-1]]
    return {
        "rows": n,
        "returned": len(sampled),
        "truncated": True,
        "policy": f"every-{step}th-row (even stride; last bar pinned)",
        "hint": "narrow the date range, coarsen interval, or set max_rows=0 for all rows",
        "data": sampled,
    }


@mcp.tool
def get_market_data(
    codes: list[str],
    start_date: str,
    end_date: str,
    source: str = "auto",
    interval: str = "1D",
    max_rows: int = DEFAULT_MAX_ROWS,
) -> str:
    """Fetch OHLCV market data for stocks, crypto, or mixed symbols.

    Supported sources:
    - "mootdx": China A-shares via TDX TCP (free, fastest, no API key, e.g. 000001.SZ, 600519.SH) — RECOMMENDED for A-shares
    - "eastmoney": China A-shares via HTTP K-line (free, stable, no API key)
    - "tencent": China A-shares, HK stocks (free, real-time, no API key)
    - "baidu": China A-shares (free, K-line with MA, no API key)
    - "tushare": China A-shares (requires TUSHARE_TOKEN, e.g. 000001.SZ)
    - "yfinance": HK/US equities (free, e.g. AAPL.US, 700.HK)
    - "akshare": A-shares, US, HK, futures, forex (free, e.g. 000001.SZ, AAPL.US)
    - "okx": cryptocurrency (free, e.g. BTC-USDT, ETH-USDT)
    - "ccxt": crypto from 100+ exchanges (free, e.g. BTC/USDT)
    - "twelvedata": global all-markets (requires TWELVE_DATA_API_KEY)
    - "finnhub": US stocks (requires FINNHUB_API_KEY)
    - "futu": A-shares, HK stocks (requires FutuOpenD running locally)
    - "coingecko": crypto market cap & trending (free)
    - "global_indices": global stock indices via yfinance (free)
    - "commodities": metals, energy, agricultural via yfinance (free)
    - "auto": auto-detect based on symbol format with market-level fallback chains

    Args:
        codes: List of symbols (e.g. ["AAPL.US", "BTC-USDT", "000001.SZ"]).
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        source: Data source ("auto", "mootdx", "eastmoney", "tencent", "baidu", "tushare", "yfinance", "akshare", "okx", "ccxt", "twelvedata", "finnhub", "futu", "coingecko", "global_indices", "commodities").
        interval: Bar size (1m/5m/15m/30m/1H/4H/1D, default "1D").
        max_rows: Per-symbol row cap (default 250) so the response stays
            within the MCP token budget. A symbol exceeding it returns an
            even-stride downsample (every step-th bar, last bar pinned)
            plus truncation metadata. Set max_rows=0 for all rows
            (unbounded, legacy behavior).
    """
    _ensure_data_tokens()

    results = {}

    if source == "auto":
        groups: dict[str, list[str]] = {}
        for code in codes:
            src = _detect_source(code)
            groups.setdefault(src, []).append(code)
    else:
        groups = {source: list(codes)}

    _unresolved_errors: dict[str, str] = {}

    for src, src_codes in groups.items():
        loader_cls = _get_loader(src)
        loader = loader_cls()
        try:
            data_map = loader.fetch(src_codes, start_date, end_date, interval=interval)
        except Exception as exc:
            # A loader blow-up for one group must not lose already-resolved
            # symbols or surface as an opaque MCP error; those codes fall
            # through to _unresolved below (P05).
            logger.exception("market-data loader %r failed for %s; codes fall through to _unresolved", src, src_codes)
            for c in src_codes:
                _unresolved_errors[c] = f"loader {src} failed: {exc}"
            data_map = {}
        for symbol, df in data_map.items():
            records = df.reset_index().to_dict(orient="records")
            for r in records:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()
                    elif hasattr(v, "item"):
                        r[k] = v.item()
            results[symbol] = _cap_rows(records, max_rows)

    # P05: surface unresolved codes with error reasons when available.
    unresolved = [c for c in codes if c not in results]
    if unresolved:
        results["_unresolved"] = [
            {"code": c, "reason": _unresolved_errors.get(c, "no data returned")}
            for c in unresolved
        ]

    return json.dumps(results, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Swarm status & history tools
# ---------------------------------------------------------------------------


def _get_swarm_store():
    from src.swarm.store import SwarmStore, swarm_runs_root

    swarm_dir = swarm_runs_root()
    swarm_dir.mkdir(parents=True, exist_ok=True)
    return SwarmStore(base_dir=swarm_dir)


def _run_to_dict(run) -> dict:
    from src.swarm.serialization import run_level_error, serialize_task

    return {
        "run_id": run.id,
        "status": run.status.value,
        "preset": run.preset_name,
        "created_at": run.created_at,
        "error": run_level_error(run),
        "tasks": [serialize_task(t) for t in run.tasks],
        "final_report": run.final_report,
        "total_input_tokens": run.total_input_tokens,
        "total_output_tokens": run.total_output_tokens,
    }


@mcp.tool
def get_swarm_status(run_id: str) -> str:
    """Get the current status of a swarm run.

    Returns status, task progress, and token usage for the specified run.
    Use this to poll a long-running swarm without blocking.

    Args:
        run_id: The run ID returned by run_swarm.
    """
    store = _get_swarm_store()
    run = store.load_run(run_id)
    if run is None:
        return json.dumps({"status": "error", "error": f"Run {run_id} not found"}, ensure_ascii=False)
    return json.dumps(_run_to_dict(run), ensure_ascii=False, indent=2)


@mcp.tool
def get_run_result(run_id: str) -> str:
    """Get the final report and task summaries of a completed swarm run.

    Returns the final_report text and per-task summaries. If the run is
    still in progress, returns current status instead.

    Args:
        run_id: The run ID returned by run_swarm.
    """
    store = _get_swarm_store()
    run = store.load_run(run_id)
    if run is None:
        return json.dumps({"status": "error", "error": f"Run {run_id} not found"}, ensure_ascii=False)
    return json.dumps(_run_to_dict(run), ensure_ascii=False, indent=2)


@mcp.tool
def list_runs(limit: int = 20) -> str:
    """List recent swarm runs sorted by creation time (newest first).

    Returns run IDs, presets, statuses, and creation timestamps.
    Use get_run_result(run_id) to fetch full details for a specific run.

    Args:
        limit: Maximum number of runs to return (default 20).
    """
    store = _get_swarm_store()
    runs = store.list_runs(limit=limit)
    items = []
    for run in runs:
        items.append(
            {
                "run_id": run.id,
                "preset": run.preset_name,
                "status": run.status.value,
                "created_at": run.created_at,
                "total_input_tokens": run.total_input_tokens,
                "total_output_tokens": run.total_output_tokens,
            }
        )
    return json.dumps(items, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Trade journal tool
# ---------------------------------------------------------------------------


@mcp.tool
def analyze_trade_journal(
    file_path: str,
    analysis_type: str = "full",
    filter_expr: str = "",
) -> str:
    """Analyze a user's trade journal (CSV/Excel broker export) and return
    a trading profile plus behavior diagnostics.

    Parses 同花顺 / 东方财富 / 富途 / generic formats (encoding auto-detected).
    Output (JSON):
      - profile: holding days, frequency, win rate, PnL ratio, top symbols,
                 market distribution, hourly distribution
      - behaviors: disposition effect, overtrading, chasing momentum,
                   anchoring (each with severity + numeric evidence)

    Args:
        file_path: Absolute path to the uploaded CSV/Excel file.
        analysis_type: "full" | "profile" | "behavior" | "strategy".
        filter_expr: Optional filter (e.g. "2026-01 to 2026-03",
                     "symbol=600519.SH", "market=china_a").
    """
    registry = _get_registry()
    return registry.execute(
        "analyze_trade_journal",
        {
            "file_path": file_path,
            "analysis_type": analysis_type,
            "filter_expr": filter_expr,
        },
    )


# ---------------------------------------------------------------------------
# Shadow Account tools (4)
# ---------------------------------------------------------------------------


@mcp.tool
def extract_shadow_strategy(
    journal_path: str,
    min_support: int = 3,
    max_rules: int = 5,
) -> str:
    """Extract a Shadow Account profile (3-5 human-readable if-then rules)
    from the user's profitable roundtrips in a trade journal.

    Run `analyze_trade_journal` first if the journal hasn't been parsed.
    Returns shadow_id + rules preview. Profile persists to
    ~/.AStockPursue/shadow_accounts/.

    Args:
        journal_path: Path to the CSV/Excel broker export.
        min_support: Minimum profitable roundtrips required to back one rule.
        max_rules: Maximum rules to return (typically 3-5).
    """
    registry = _get_registry()
    return registry.execute(
        "extract_shadow_strategy",
        {
            "journal_path": journal_path,
            "min_support": min_support,
            "max_rules": max_rules,
        },
    )


@mcp.tool
def run_shadow_backtest(
    shadow_id: str,
    window_start: str = "",
    window_end: str = "",
    markets: list[str] | None = None,
    journal_path: str = "",
) -> str:
    """Run a multi-market backtest (A股/港股/美股/crypto) on a Shadow Account
    profile and compute delta-PnL attribution vs the user's realized trades.

    Requires `extract_shadow_strategy` to have run first.

    Args:
        shadow_id: ID returned by extract_shadow_strategy.
        window_start: ISO date, default today-1y.
        window_end: ISO date, default today.
        markets: Subset of ["china_a", "hk", "us", "crypto"], default all four.
        journal_path: Original journal path (enables attribution), optional.
    """
    registry = _get_registry()
    params: dict[str, Any] = {"shadow_id": shadow_id}
    if window_start:
        params["window_start"] = window_start
    if window_end:
        params["window_end"] = window_end
    if markets:
        params["markets"] = markets
    if journal_path:
        params["journal_path"] = journal_path
    return registry.execute("run_shadow_backtest", params)


@mcp.tool
def render_shadow_report(
    shadow_id: str,
    include_today_signals: bool = True,
    window_start: str = "",
    window_end: str = "",
    journal_path: str = "",
) -> str:
    """Render the Shadow Account HTML/PDF report (8 sections + charts) for
    a shadow_id. If no cached backtest, one is run automatically.

    Args:
        shadow_id: Shadow Account ID.
        include_today_signals: Include today's market scan section.
        window_start: Optional backtest window override.
        window_end: Optional backtest window override.
        journal_path: Original journal path (for attribution), optional.
    """
    registry = _get_registry()
    params: dict[str, Any] = {
        "shadow_id": shadow_id,
        "include_today_signals": include_today_signals,
    }
    if window_start:
        params["window_start"] = window_start
    if window_end:
        params["window_end"] = window_end
    if journal_path:
        params["journal_path"] = journal_path
    return registry.execute("render_shadow_report", params)


@mcp.tool
def scan_shadow_signals(
    shadow_id: str,
    date: str = "",
    per_market: int = 3,
) -> str:
    """List today's symbols that match the Shadow Account's entry cadence
    (research use only — not a trade recommendation).

    Args:
        shadow_id: Shadow Account ID.
        date: ISO YYYY-MM-DD target date, default today.
        per_market: Max signals per market.
    """
    registry = _get_registry()
    params: dict[str, Any] = {"shadow_id": shadow_id, "per_market": per_market}
    if date:
        params["date"] = date
    return registry.execute("scan_shadow_signals", params)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Entry point for `AStockPursue-mcp` CLI command."""
    global _include_shell_tools, _registry
    import argparse

    parser = argparse.ArgumentParser(description="AStockPursue MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio",
                        help="MCP transport (default: stdio)")
    parser.add_argument("--port", type=int, default=8900,
                        help="HTTP port (only used with --transport sse / streamable-http)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="HTTP bind address (only used with --transport sse / streamable-http)")
    parser.add_argument("--path", default="/mcp",
                        help="HTTP endpoint path (only used with --transport streamable-http)")
    args = parser.parse_args()
    _include_shell_tools = True if args.transport == "stdio" else _env_shell_tools_enabled()
    _registry = None
    _get_registry()  # pre-warm: avoids deadlock when first tools/call lazy-inits inside FastMCP worker thread

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port, host=args.host)
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", port=args.port, host=args.host, path=args.path)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
