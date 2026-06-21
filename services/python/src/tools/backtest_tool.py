"""Backtest execution tool: validates config.json + signal_engine.py, delegates to Go REST API."""

from __future__ import annotations

import json
import logging

from src.agent.progress import emit_progress
from src.agent.tools import BaseTool
from src.tools.path_utils import safe_run_dir

logger = logging.getLogger(__name__)

# Known data sources — kept in sync with DataService gRPC (data_service.py).
# The DataService validates source names server-side; this list is a
# lightweight client-side pre-check to give fast feedback.
_VALID_SOURCES = frozenset({
    "auto", "mootdx", "tushare", "akshare", "futu",
    "yfinance", "okx", "eastmoney", "tencent", "baidu",
    "ccxt", "coingecko", "sina", "twelvedata",
})


def run_backtest(run_dir: str) -> str:
    """Run backtest: validate config.json + signal_engine.py, call Go REST API.

    Args:
        run_dir: Path to the run directory.

    Returns:
        JSON-formatted execution result.
    """
    emit_progress("validate", message="validating run_dir and config")
    try:
        run_path = safe_run_dir(run_dir)
    except ValueError as exc:
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)

    config_path = run_path / "config.json"
    if not config_path.exists():
        return json.dumps({"status": "error", "error": "config.json not found"}, ensure_ascii=False)

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "error": f"config.json parse error: {e}"}, ensure_ascii=False)

    # --- lightweight source validation (server-side validated by DataService as well) ---
    source = config.get("source")
    if not source:
        return json.dumps({"status": "error", "error": "config.json missing 'source' field"}, ensure_ascii=False)
    if source not in _VALID_SOURCES:
        return json.dumps({"status": "error", "error": f"unknown source: {source} (valid: {sorted(_VALID_SOURCES)})"}, ensure_ascii=False)

    signal_path = run_path / "code" / "signal_engine.py"
    if not signal_path.exists():
        return json.dumps({"status": "error", "error": "code/signal_engine.py not found"}, ensure_ascii=False)

    # Extract backtest parameters from config (supports both old and new key names)
    symbols = config.get("symbols") or config.get("codes", [])
    if not symbols:
        return json.dumps({"status": "error", "error": "config.json missing 'symbols' or 'codes' field"}, ensure_ascii=False)
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(",") if s.strip()]

    start_date = config.get("start_date", "2024-01-01")
    end_date = config.get("end_date", "2025-12-31")
    frequency = (config.get("frequency") or config.get("interval", "1d")).lower()
    initial_cash = float(config.get("initial_capital") or config.get("initial_cash", 100000))

    emit_progress(
        "simulate",
        message=f"running Go backtest: {len(symbols)} symbols, {start_date}→{end_date}, {frequency}",
    )

    # --- delegate to Go REST API ---
    try:
        from src.go_http import run_backtest as go_run_backtest
        bt_req = {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
            "initial_cash": initial_cash,
        }
        resp = go_run_backtest(bt_req)
    except Exception as exc:
        logger.exception("Go backtest API failed")
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)

    if "error" in resp:
        return json.dumps({"status": "error", "error": resp["error"]}, ensure_ascii=False)

    # Unwrap Go response envelope: {id, result: BacktestResult}
    result = resp.get("result", resp)

    emit_progress("finalize", message="backtest complete")
    return json.dumps({
        "status": "ok",
        "metrics": {
            "total_return": result.get("total_return", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "max_drawdown": result.get("max_drawdown", 0),
            "win_rate": result.get("win_rate", 0),
            "total_trades": result.get("total_trades", 0),
        },
        "run_dir": run_dir,
    }, ensure_ascii=False)


class BacktestTool(BaseTool):
    """Backtest execution tool — delegates to Go REST API."""

    name = "backtest"
    description = "Run backtest: validate config.json + signal_engine.py, call Go backtest engine."
    parameters = {
        "type": "object",
        "properties": {
            "run_dir": {"type": "string", "description": "Path to the run directory"},
        },
        "required": ["run_dir"],
    }
    repeatable = True
    is_readonly = False

    def execute(self, **kwargs) -> str:
        """Execute backtest via Go REST API."""
        return run_backtest(kwargs["run_dir"])
