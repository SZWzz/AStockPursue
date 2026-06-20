"""Output nodes — Report, notify, export, chart data, and factor persistence.

These nodes consume upstream pipeline results and produce final outputs:
- ReportGeneratorNode: formats a structured text report from analysis data
- NotifyNode: sends results via webhook, email, or console
- ExportNode: exports DataFrame results to a file format
- ChartDataNode: formats backtest/OHLCV/indicator data for frontend ECharts
- FactorPersistNode: saves discovered factors to FactorKB + promotes to Alpha Zoo
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import NodePort, PortType

logger = logging.getLogger(__name__)


@register_node
class ReportGeneratorNode(BaseNode):
    node_type = "report"; category = "output"; label = "Report Generator"
    description = (
        "Generate a structured text report from upstream analysis results. "
        "Consumes backtest, attribution, comparison, correlation, or sentiment data "
        "and formats a readable summary with key findings."
    )
    icon = "FileText"
    inputs = [
        BaseNode.in_port("data", PortType.ANY,
                         description="Any upstream analysis result (backtest, attribution, comparison, etc.)"),
    ]
    outputs = [
        BaseNode.out_port("report", PortType.PARAMS,
                          description="Generated report with title, sections, and summary"),
    ]
    config_schema = {
        "title": {
            "title": "Report Title", "type": "string", "default": "Quantitative Analysis Report",
        },
        "include_raw_data": {
            "title": "Include Raw Data", "type": "boolean", "default": False,
            "description": "Include raw metrics in the report appendix",
        },
        "format": {
            "title": "Format", "type": "string",
            "enum": ["markdown", "text", "json"], "default": "markdown",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        data = inputs.get("data", {})
        title = config.get("title", "Quantitative Analysis Report")
        include_raw = config.get("include_raw_data", False)
        fmt = config.get("format", "markdown")

        if data is None or (isinstance(data, dict) and not data):
            return {"report": {"title": title, "sections": [], "error": "No input data"}}

        sections: List[Dict[str, Any]] = []
        raw_data: Dict[str, Any] = {}

        if isinstance(data, dict):
            # ── Backtest section ──────────────────────────────────────────────
            if "metrics" in data or "summary" in data:
                sections.append(self._backtest_section(data))
                if include_raw:
                    raw_data["backtest"] = data

            # ── Attribution section ───────────────────────────────────────────
            if any(k in data for k in ("brinson", "factor_attribution", "sector")):
                sections.append(self._attribution_section(data))
                if include_raw:
                    raw_data["attribution"] = data

            # ── Comparison section ────────────────────────────────────────────
            if "winner" in data or "paired_t" in data:
                sections.append(self._comparison_section(data))
                if include_raw:
                    raw_data["comparison"] = data

            # ── Correlation section ───────────────────────────────────────────
            if "matrix" in data and "summary" in data:
                sections.append(self._correlation_section(data))
                if include_raw:
                    raw_data["correlation"] = data

            # ── Factor section ────────────────────────────────────────────────
            if "factors" in data:
                sections.append(self._factor_section(data))
                if include_raw:
                    raw_data["factors"] = data

            # ── Sentiment section ─────────────────────────────────────────────
            if "scores" in data:
                sections.append(self._sentiment_section(data))
                if include_raw:
                    raw_data["sentiment"] = data

            # ── Generic fallback ──────────────────────────────────────────────
            if not sections:
                sections.append(self._generic_section(data))
                if include_raw:
                    raw_data["input"] = data

        elif isinstance(data, (list, str)):
            sections.append(self._generic_section({"data": data}))

        # ── Assemble report ───────────────────────────────────────────────────
        report = {
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "format": fmt,
            "sections": sections,
            "n_sections": len(sections),
        }
        if include_raw:
            report["appendix"] = raw_data

        # ── Render to requested format ────────────────────────────────────────
        if fmt == "markdown":
            report["rendered"] = self._render_markdown(title, sections)
        elif fmt == "text":
            report["rendered"] = self._render_text(title, sections)

        logger.info("Report: %d sections generated (format=%s)", len(sections), fmt)
        return {"report": report}

    # ── Section builders ──────────────────────────────────────────────────────

    def _backtest_section(self, data: dict) -> dict:
        m = data.get("metrics", data.get("summary", {}))
        lines = []
        for k in ("total_return", "annual_return", "sharpe", "max_drawdown", "win_rate", "trade_count"):
            if k in m and m[k] is not None:
                val = m[k]
                lines.append(f"  - **{k}**: {val:.4f}" if isinstance(val, float) else f"  - **{k}**: {val}")
        return {"heading": "Backtest Performance", "body": "\n".join(lines), "type": "backtest"}

    def _attribution_section(self, data: dict) -> dict:
        lines = []
        summary = data.get("summary", {})
        if summary:
            for k, v in list(summary.items())[:8]:
                lines.append(f"  - **{k}**: {v}")
        for method in ("brinson", "factor_attribution", "sector"):
            if method in data and "error" not in str(data[method]):
                lines.append(f"  - {method}: available")
        return {"heading": "Performance Attribution", "body": "\n".join(lines) if lines else "Attribution data available", "type": "attribution"}

    def _comparison_section(self, data: dict) -> dict:
        lines = []
        winner = data.get("winner", {})
        if winner:
            lines.append("**Winner by metric:**")
            for k, v in winner.items():
                if v != "tie":
                    lines.append(f"  - {k}: Strategy {v}")
        bootstrap = data.get("bootstrap", {})
        if "prob_a_better_than_b" in bootstrap:
            lines.append(f"  - Probability A > B: {bootstrap['prob_a_better_than_b']:.2%}")
        return {"heading": "Strategy Comparison", "body": "\n".join(lines), "type": "comparison"}

    def _correlation_section(self, data: dict) -> dict:
        s = data.get("summary", {})
        labels = data.get("labels", [])
        lines = [
            f"  - Assets: {len(labels)}",
            f"  - Mean correlation: {s.get('mean_corr', '?')}",
            f"  - Method: {s.get('method', '?')}, Lookback: {s.get('lookback_days', '?')} days",
        ]
        return {"heading": "Correlation Analysis", "body": "\n".join(lines), "type": "correlation"}

    def _factor_section(self, data: dict) -> dict:
        factors = data.get("factors", [])
        lines = [f"  - Factors discovered: {len(factors)}"]
        for f in factors[:5]:
            if isinstance(f, dict):
                lines.append(f"  - fitness={f.get('fitness', '?')}, IC={f.get('ic_train', '?')} | `{str(f.get('formula', ''))[:50]}`")
        return {"heading": "Factor Discovery", "body": "\n".join(lines), "type": "factor"}

    def _sentiment_section(self, data: dict) -> dict:
        scores = data.get("scores", {})
        overall = data.get("overall_mean")
        lines = [f"  - Articles analyzed: {data.get('n_articles', '?')}"]
        if overall is not None:
            sentiment_label = "Bullish" if overall > 0.6 else "Bearish" if overall < 0.4 else "Neutral"
            lines.append(f"  - Overall mean: {overall:.3f} ({sentiment_label})")
        if scores:
            top_stocks = sorted(scores.items(), key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0, reverse=True)[:5]
            for sym, info in top_stocks:
                if isinstance(info, dict):
                    lines.append(f"  - {sym}: {info.get('count', 0)} articles, mean={info.get('mean_sentiment', '?')}")
        return {"heading": "Sentiment Analysis", "body": "\n".join(lines), "type": "sentiment"}

    def _generic_section(self, data: dict) -> dict:
        keys = [k for k in data.keys() if not k.startswith("_")][:10]
        lines = [f"  - {k}: {type(data[k]).__name__}" for k in keys]
        return {"heading": "Analysis Results", "body": "\n".join(lines) if lines else "Data available", "type": "generic"}

    # ── Renderers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _render_markdown(title: str, sections: list) -> str:
        lines = [f"# {title}", f"\n*Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n"]
        for sec in sections:
            lines.append(f"## {sec['heading']}")
            lines.append(sec["body"])
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_text(title: str, sections: list) -> str:
        sep = "=" * 60
        lines = [sep, title, sep, ""]
        for sec in sections:
            lines.append(f"--- {sec['heading']} ---")
            lines.append(sec["body"])
            lines.append("")
        return "\n".join(lines)


@register_node
class NotifyNode(BaseNode):
    node_type = "notify"; category = "output"; label = "Notify"
    description = (
        "Send workflow results via webhook, email, or console output. "
        "Useful for alerting on backtest completion or factor discovery."
    )
    icon = "Bell"
    resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("data", PortType.ANY,
                         description="Data to include in the notification"),
        BaseNode.in_port("report", PortType.PARAMS, required=False,
                         description="Optional pre-formatted report from ReportGeneratorNode"),
    ]
    outputs = [
        BaseNode.out_port("notify_result", PortType.PARAMS,
                          description="Notification delivery status"),
    ]
    config_schema = {
        "channel": {
            "title": "Channel", "type": "string",
            "enum": ["console", "webhook", "email"], "default": "console",
        },
        "webhook_url": {
            "title": "Webhook URL", "type": "string", "default": "",
            "description": "Required when channel is 'webhook'",
        },
        "email_to": {
            "title": "Email To", "type": "string", "default": "",
            "description": "Comma-separated. Required when channel is 'email'",
        },
        "subject": {
            "title": "Subject", "type": "string", "default": "Workflow Notification",
        },
        "max_payload_chars": {
            "title": "Max Payload Chars", "type": "integer", "default": 4000,
            "minimum": 100, "maximum": 50000,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        channel = config.get("channel", "console")
        subject = config.get("subject", "Workflow Notification")
        max_chars = int(config.get("max_payload_chars", 4000))

        # ── Build payload ─────────────────────────────────────────────────────
        report = inputs.get("report", {})
        data = inputs.get("data", {})

        if isinstance(report, dict) and report.get("rendered"):
            body = report["rendered"]
        elif isinstance(report, dict) and report.get("sections"):
            body = ReportGeneratorNode._render_text(report.get("title", "Report"), report["sections"])
        else:
            body = json.dumps(data, indent=2, default=str, ensure_ascii=False) if isinstance(data, dict) else str(data)

        # Truncate
        if len(body) > max_chars:
            body = body[:max_chars] + "\n\n[truncated]"

        result = {"channel": channel, "subject": subject, "chars": len(body)}

        if channel == "console":
            logger.info("Notify [%s]: %s\n%s", subject, "-" * 40, body[:500])
            result["status"] = "logged"

        elif channel == "webhook":
            webhook_url = config.get("webhook_url", "").strip()
            if not webhook_url:
                return {"notify_result": {"error": "webhook_url is required for webhook channel"}}
            try:
                import urllib.request
                payload = json.dumps({"subject": subject, "body": body, "timestamp": datetime.now(timezone.utc).isoformat()}).encode()
                req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result["status"] = "sent"
                    result["http_status"] = resp.status
            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)

        elif channel == "email":
            email_to = config.get("email_to", "").strip()
            if not email_to:
                return {"notify_result": {"error": "email_to is required for email channel"}}
            try:
                from src.notify.engine import NotifyEngine
                engine = NotifyEngine()
                engine.send_alert(subject=subject, body=body, recipients=email_to.split(","))
                result["status"] = "sent"
            except (ImportError, Exception) as e:
                result["status"] = "failed"
                result["error"] = str(e)

        logger.info("Notify: channel=%s status=%s", channel, result.get("status"))
        return {"notify_result": result}


@register_node
class ExportNode(BaseNode):
    node_type = "export"; category = "output"; label = "Export Data"
    description = (
        "Export workflow data to a file. Supports CSV, JSON, and Parquet formats. "
        "Outputs the file path for downstream consumption."
    )
    icon = "Download"
    resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("data", PortType.ANY,
                         description="Data to export (DataFrame, dict, or list)"),
    ]
    outputs = [
        BaseNode.out_port("export_result", PortType.PARAMS,
                          description="Export result with file path and statistics"),
    ]
    config_schema = {
        "format": {
            "title": "Format", "type": "string",
            "enum": ["csv", "json", "parquet"], "default": "csv",
        },
        "filename": {
            "title": "Filename", "type": "string", "default": "",
            "description": "Output filename (without extension). Empty = auto-generated.",
        },
        "output_dir": {
            "title": "Output Dir", "type": "string", "default": "",
            "description": "Output directory. Empty = temp directory.",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        data = inputs.get("data")
        fmt = config.get("format", "csv")
        filename = config.get("filename", "").strip()
        output_dir = config.get("output_dir", "").strip()

        if data is None:
            return {"export_result": {"error": "No data to export"}}

        import os
        import tempfile
        from pathlib import Path

        # ── Resolve output path ───────────────────────────────────────────────
        if output_dir:
            out_path = Path(output_dir)
        else:
            out_path = Path(tempfile.mkdtemp(prefix="wf_export_"))

        out_path.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = filename or f"workflow_export_{ts}"
        filepath = out_path / f"{name}.{fmt}"

        # ── Export ────────────────────────────────────────────────────────────
        stats: Dict[str, Any] = {"format": fmt, "filepath": str(filepath)}

        try:
            if isinstance(data, pd.DataFrame):
                stats["shape"] = list(data.shape)
                if fmt == "csv":
                    data.to_csv(filepath, index=True)
                elif fmt == "json":
                    data.to_json(filepath, orient="records", indent=2)
                elif fmt == "parquet":
                    data.to_parquet(filepath, index=True)

            elif isinstance(data, dict):
                # Try converting nested DataFrames
                serializable = {}
                df_count = 0
                for k, v in data.items():
                    if isinstance(v, pd.DataFrame):
                        df_count += 1
                        serializable[k] = f"<DataFrame: {v.shape[0]}x{v.shape[1]}>"
                    elif isinstance(v, (str, int, float, bool, list, dict)):
                        serializable[k] = v
                    else:
                        serializable[k] = str(v)[:200]
                stats["keys"] = len(data)
                stats["dataframe_keys"] = df_count
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

            elif isinstance(data, list):
                stats["length"] = len(data)
                with open(filepath, "w", encoding="utf-8") as f:
                    if fmt == "csv" and data and isinstance(data[0], dict):
                        import csv
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
                    else:
                        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            else:
                # Fallback: write string representation
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(str(data))

            stats["size_bytes"] = filepath.stat().st_size if filepath.exists() else 0
            stats["filename"] = filepath.name

            logger.info("Export: %s (%d bytes)", filepath, stats["size_bytes"])
            return {"export_result": {"status": "exported", "stats": stats}}

        except Exception as e:
            logger.exception("Export failed")
            return {"export_result": {"error": str(e)}}


@register_node
class ChartDataNode(BaseNode):
    node_type = "chart_data"; category = "output"; label = "Chart Data"
    description = (
        "Format backtest results + OHLCV + indicators into structured chart data "
        "compatible with the frontend CandlestickChart and EquityChart components. "
        "Outputs OHLCV bars, equity curve, trade markers, and indicator overlays."
    )
    icon = "BarChart3"
    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT, required=False,
                         description="Backtest result with metrics, equity curve, trade markers"),
        BaseNode.in_port("ohlcv_data", PortType.DF_OHLCV, required=False,
                         description="OHLCV data for candlestick chart"),
        BaseNode.in_port("indicators", PortType.DF_FACTOR, required=False,
                         description="Technical indicators for overlay on price chart"),
        BaseNode.in_port("signal", PortType.SIGNAL, required=False,
                         description="Trading signal (used to derive trade markers if not in backtest)"),
    ]
    outputs = [
        BaseNode.out_port("chart_payload", PortType.PARAMS,
                          description="Chart-ready JSON payload for frontend ECharts components"),
    ]
    config_schema = {
        "chart_types": {
            "title": "Chart Types", "type": "string",
            "enum": ["all", "candlestick", "equity", "metrics", "indicators"],
            "default": "all",
            "description": "Which chart datasets to include",
        },
        "max_bars": {
            "title": "Max Bars", "type": "integer", "default": 500,
            "minimum": 10, "maximum": 5000,
            "description": "Max OHLCV bars to include (truncate older data)",
        },
        "include_trades": {
            "title": "Include Trades", "type": "boolean", "default": True,
        },
        "indicator_overlay": {
            "title": "Indicator Overlay", "type": "string",
            "enum": ["none", "rsi", "sma", "all"], "default": "all",
            "description": "Which indicators to include as chart overlays",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        chart_types = config.get("chart_types", "all")
        max_bars = int(config.get("max_bars", 500))
        include_trades = config.get("include_trades", True)
        indicator_overlay = config.get("indicator_overlay", "all")

        payload: Dict[str, Any] = {"charts": {}}

        bt = inputs.get("backtest_result", {})
        if isinstance(bt, dict) and bt.get("error"):
            return {"chart_payload": {"error": bt["error"], "charts": {}}}

        ohlcv = inputs.get("ohlcv_data", {})
        if isinstance(ohlcv, pd.DataFrame):
            ohlcv = {"panel": ohlcv}

        indicators = inputs.get("indicators")
        signal = inputs.get("signal", {})

        # ── 1. Candlestick (OHLCV bars) ───────────────────────────────────
        if chart_types in ("all", "candlestick") and ohlcv:
            bars_data = self._build_bars(ohlcv, max_bars)
            payload["charts"]["candlestick"] = bars_data

        # ── 2. Equity curve + drawdown ────────────────────────────────────
        if chart_types in ("all", "equity"):
            equity_data = self._build_equity(bt, ohlcv)
            if equity_data:
                payload["charts"]["equity"] = equity_data

        # ── 3. Trade markers ──────────────────────────────────────────────
        if chart_types in ("all", "candlestick") and include_trades:
            trades = self._build_trades(bt, signal)
            if trades:
                payload["charts"]["trades"] = trades

        # ── 4. Metrics dashboard ──────────────────────────────────────────
        if chart_types in ("all", "metrics"):
            metrics_data = self._build_metrics(bt)
            if metrics_data:
                payload["charts"]["metrics"] = metrics_data

        # ── 5. Indicator overlays ─────────────────────────────────────────
        if chart_types in ("all", "indicators") and indicators is not None:
            indicator_data = self._build_indicators(indicators, indicator_overlay, max_bars)
            if indicator_data:
                payload["charts"]["indicators"] = indicator_data

        # ── Summary ───────────────────────────────────────────────────────
        payload["summary"] = {
            "chart_types": [k for k, v in payload["charts"].items() if v],
            "n_charts": len(payload["charts"]),
        }

        logger.info("ChartData: %d chart datasets generated", len(payload["charts"]))
        return {
            "chart_payload": payload,
            "_summary": {"chart_payload": payload},
        }

    # ── Builders ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_bars(ohlcv: dict, max_bars: int) -> dict:
        """Build OHLCV candlestick bars in PriceBar format."""
        all_bars: Dict[str, list] = {}
        for code, df in ohlcv.items():
            if not isinstance(df, pd.DataFrame):
                continue
            df_slice = df.tail(max_bars) if len(df) > max_bars else df
            bars = []
            for idx, row in df_slice.iterrows():
                bars.append({
                    "time": str(idx),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                })
            all_bars[code] = bars

        return {
            "type": "candlestick",
            "codes": list(all_bars.keys()),
            "series": all_bars,
            "n_bars": sum(len(b) for b in all_bars.values()),
        }

    @staticmethod
    def _build_equity(bt: dict, ohlcv: dict) -> dict | None:
        """Build equity curve + drawdown series.

        Handles multiple equity data formats:
        - New format: list of {"time": ..., "equity": ...} dicts from BacktestNode
        - Legacy: flat number list, pd.Series, or np.ndarray
        - Fallback: naive buy-and-hold approximation from OHLCV close prices
        """
        equity = None
        equity_times = None

        # Try backtest equity curve first
        if isinstance(bt, dict):
            eq = bt.get("equity_curve") or bt.get("equity")
            if isinstance(eq, list) and len(eq) > 0:
                first = eq[0]
                if isinstance(first, dict) and "equity" in first:
                    # New format: [{time, equity}] dicts from BacktestNode
                    equity = [float(p["equity"]) for p in eq]
                    equity_times = [p.get("time") for p in eq]
                else:
                    # Flat number list
                    equity = [float(v) for v in eq]
            elif isinstance(eq, pd.Series):
                equity = eq.tolist()
            elif isinstance(eq, np.ndarray):
                equity = eq.tolist()

        # Fallback: build from OHLCV if only one code
        if equity is None and ohlcv:
            for df in ohlcv.values():
                if isinstance(df, pd.DataFrame) and "close" in df.columns:
                    # Simple: assume buy-and-hold, equity = close / close[0] * 1000000
                    close = df["close"].dropna()
                    if len(close) > 0:
                        equity = (close / close.iloc[0] * 1_000_000).tolist()
                    break

        if equity is None or len(equity) < 2:
            return None

        # Compute drawdown
        peak = equity[0]
        drawdown: List[float] = []
        for v in equity:
            if v > peak:
                peak = v
            dd = (v - peak) / peak if peak > 0 else 0
            drawdown.append(round(dd, 4))

        # Build EquityPoint-style data with real timestamps
        points = []
        for i, (eq_val, dd_val) in enumerate(zip(equity, drawdown)):
            time_label = equity_times[i] if equity_times and i < len(equity_times) else f"T{i}"
            points.append({
                "time": time_label,
                "equity": round(float(eq_val), 2),
                "drawdown": dd_val,
            })

        # Sample if too many points
        if len(points) > 500:
            step = len(points) // 500
            points = points[::step]

        return {
            "type": "equity",
            "points": points,
            "final_equity": points[-1]["equity"] if points else 0,
            "max_drawdown": min(p["drawdown"] for p in points) if points else 0,
        }

    @staticmethod
    def _build_trades(bt: dict, signal: dict) -> list | None:
        """Build trade markers from backtest or signal."""
        trades = None
        if isinstance(bt, dict):
            trades = bt.get("trades") or bt.get("trade_markers")
            if isinstance(trades, list):
                return [{
                    "time": t.get("time", t.get("timestamp", "")),
                    "side": t.get("side", "BUY"),
                    "price": float(t.get("price", 0)),
                    "code": t.get("code", t.get("symbol", "")),
                    "reason": t.get("reason", ""),
                } for t in trades[:200] if t.get("time")]

        # Fallback: derive from signal changes
        if trades is None and isinstance(signal, dict) and signal:
            trades = []
            # Simplistic: first non-zero signal entry = BUY, last = SELL
            for code, s in signal.items():
                if isinstance(s, pd.Series):
                    non_zero = s[s.abs() > 0.001]
                    if len(non_zero) > 0:
                        trades.append({
                            "time": str(non_zero.index[0]),
                            "side": "BUY" if non_zero.iloc[0] > 0 else "SELL",
                            "price": 0,
                            "code": code,
                            "reason": "signal_entry",
                        })

        return trades[:200] if trades else None

    @staticmethod
    def _build_metrics(bt: dict) -> dict | None:
        """Build metrics dashboard data."""
        if not isinstance(bt, dict):
            return None

        m = bt.get("metrics", bt.get("summary", {}))
        if not m:
            return None

        metrics = {}
        for k in ("total_return", "annual_return", "sharpe", "calmar", "sortino",
                   "max_drawdown", "win_rate", "volatility", "profit_factor", "trade_count"):
            if k in m and m[k] is not None:
                metrics[k] = round(float(m[k]), 4) if isinstance(m[k], (int, float)) else m[k]

        if not metrics:
            return None

        return {
            "type": "metrics",
            "metrics": metrics,
        }

    @staticmethod
    def _build_indicators(indicators, overlay: str, max_bars: int) -> dict | None:
        """Build indicator overlay series for chart."""
        if not isinstance(indicators, pd.DataFrame) or indicators.empty:
            return None

        df = indicators.tail(max_bars) if len(indicators) > max_bars else indicators
        series: Dict[str, list] = {}

        for col in df.columns:
            col_str = str(col)
            # Determine indicator type from column name
            if overlay == "none":
                break
            if overlay != "all":
                if overlay not in col_str.lower():
                    continue

            values = df[col].dropna()
            if len(values) < 2:
                continue

            points = []
            for idx, val in values.items():
                points.append({
                    "time": str(idx),
                    "value": round(float(val), 4),
                })
            series[col_str] = points

        if not series:
            return None

        return {
            "type": "indicators",
            "series": series,
            "n_series": len(series),
        }


@register_node
class FactorPersistNode(BaseNode):
    node_type = "factor_persist"; category = "output"; label = "Factor Persist"
    description = (
        "Save discovered factors into the FactorKnowledgeBase (auto-dedup by "
        "formula_hash) and optionally promote top-N to Alpha Zoo (mined/). "
        "Consumes factor results from GPEvolutionNode or AlphaZooNode."
    )
    icon = "Database"
    resource_profile = "io_bound"
    inputs = [
        BaseNode.in_port("factor_result", PortType.FACTOR_RESULT,
                         description="Factor result with 'factors' list (each has formula, fitness, IC)"),
        BaseNode.in_port("codes", PortType.STOCK_LIST, required=False,
                         description="Stock codes (for provenance tracking)"),
    ]
    outputs = [
        BaseNode.out_port("persist_result", PortType.PARAMS,
                          description="Persistence summary: saved, duplicated, promoted counts and IDs"),
    ]
    config_schema = {
        "source": {
            "title": "Source", "type": "string",
            "enum": ["gp_engine", "llm_miner", "manual", "workflow"], "default": "workflow",
        },
        "auto_promote_top_n": {
            "title": "Auto-Promote Top N", "type": "integer", "default": 0,
            "minimum": 0, "maximum": 20,
            "description": "Automatically promote the top-N best factors to Alpha Zoo. 0 = no auto-promote.",
        },
        "theme": {
            "title": "Theme", "type": "string", "default": "",
            "description": "Factor theme tag (momentum/volume/quality/volatility/value). Empty = auto-detect.",
        },
        "min_ic": {
            "title": "Min IC", "type": "number", "default": 0.02,
            "minimum": 0.0, "maximum": 1.0,
            "description": "Minimum absolute IC to persist. Factors below this are skipped.",
        },
        "universe": {
            "title": "Universe", "type": "string",
            "enum": ["equity_cn", "equity_us", "equity_hk", "crypto"], "default": "equity_cn",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        factor_result = inputs.get("factor_result", {})
        if isinstance(factor_result, dict) and factor_result.get("error"):
            return {"persist_result": {"error": factor_result["error"]}}

        factors = []
        if isinstance(factor_result, dict):
            factors = factor_result.get("factors", [])
        if isinstance(factor_result, list):
            factors = factor_result

        if not factors:
            return {"persist_result": {"error": "No factors to persist", "saved": 0, "duplicated": 0, "promoted": 0}}

        source = config.get("source", "workflow")
        auto_promote_n = int(config.get("auto_promote_top_n", 0))
        theme = config.get("theme", "").strip()
        min_ic = float(config.get("min_ic", 0.02))
        universe = config.get("universe", "equity_cn")

        codes = inputs.get("codes", [])
        if isinstance(codes, pd.DataFrame):
            codes = list(codes.columns) if len(codes.columns) < 100 else list(codes.index)

        saved = []
        duplicated = []
        promoted = []
        skipped = []

        try:
            from src.factors.mining.factor_kb import FactorKnowledgeBase
            from src.factors.mining.expression_tree import ExpressionTree

            kb = FactorKnowledgeBase()

            for i, f in enumerate(factors):
                if not isinstance(f, dict):
                    continue

                formula = f.get("formula", "")
                if not formula:
                    continue

                # Skip low-IC factors
                ic = f.get("ic_train") or f.get("ic_test") or f.get("fitness", 0)
                if abs(float(ic)) < min_ic:
                    skipped.append({"formula": formula[:60], "ic": float(ic), "reason": f"IC < {min_ic}"})
                    continue

                try:
                    # Parse formula into ExpressionTree
                    tree = ExpressionTree.from_formula(formula)

                    # Detect theme if not provided
                    detected_theme = self._detect_theme(formula) if not theme else theme

                    # Register in KB (auto-dedup by formula_hash)
                    entry, is_new = kb.register(
                        tree,
                        name=f.get("name", f"wf_{source}_{i}"),
                        theme=[detected_theme],
                        source=source,
                        data_source_version="workflow",
                        train_ic=float(ic),
                        test_ic=float(f.get("ic_test", 0)),
                        sharpe=float(f.get("sharpe", f.get("fitness", 0))),
                    )

                    rec = {
                        "alpha_id": entry.alpha_id,
                        "formula_hash": tree.formula_hash[:16],
                        "formula_preview": formula[:80],
                        "is_new": is_new,
                    }

                    if is_new:
                        saved.append(rec)
                    else:
                        duplicated.append(rec)

                    # Auto-promote to Alpha Zoo
                    if auto_promote_n > 0 and i < auto_promote_n and is_new:
                        try:
                            from src.factors.mining.factor_promoter import FactorPromoter
                            promoter = FactorPromoter()
                            alpha_id = promoter.promote(
                                individual=f,
                                name=entry.name,
                                theme=detected_theme,
                                universe=universe,
                                source=source,
                            )

                            # Register dynamically so it's searchable immediately
                            try:
                                from src.factors.registry import get_default_registry
                                py_path = Path(f"src/factors/zoo/mined/{alpha_id}.py")
                                reg = get_default_registry()
                                reg.register_dynamic(
                                    alpha_id=alpha_id,
                                    zoo_id="mined",
                                    py_file=py_path,
                                    meta={
                                        "id": alpha_id,
                                        "label": entry.name or alpha_id,
                                        "theme": [detected_theme],
                                        "universe": [universe],
                                        "columns_required": ["close", "volume"],
                                        "description": f"AI-discovered via {source}, IC={ic:.4f}",
                                    },
                                )
                                logger.info("FactorPersist: dynamically registered %s in Registry", alpha_id)
                            except Exception as re:
                                logger.warning("FactorPersist: dynamic register failed for %s: %s", alpha_id, re)

                            promoted.append({"alpha_id": alpha_id, "formula_preview": formula[:80]})
                        except Exception as e:
                            promoted.append({"alpha_id": "FAILED", "error": str(e), "formula_preview": formula[:60]})

                except Exception as e:
                    skipped.append({"formula": formula[:60], "reason": str(e)})

        except ImportError as e:
            return {"persist_result": {
                "error": f"Factor KB not available: {e}",
                "saved": 0, "duplicated": 0, "promoted": 0,
            }}

        logger.info("FactorPersist: %d saved, %d dup, %d promoted, %d skipped",
                     len(saved), len(duplicated), len(promoted), len(skipped))

        return {"persist_result": {
            "saved": len(saved),
            "saved_list": saved[:20],
            "duplicated": len(duplicated),
            "duplicated_list": duplicated[:10],
            "promoted": len(promoted),
            "promoted_list": promoted,
            "skipped": len(skipped),
            "skipped_list": skipped[:10],
            "total_input": len(factors),
        }}

    @staticmethod
    def _detect_theme(formula: str) -> str:
        """Auto-detect factor theme from formula operators."""
        f = formula.lower()
        if any(kw in f for kw in ("momentum", "pct_change", "return", "roc", "delta")):
            return "momentum"
        if any(kw in f for kw in ("volume", "turnover", "amount", "vwap")):
            return "volume"
        if any(kw in f for kw in ("volatility", "std", "var", "atr", "boll")):
            return "volatility"
        if any(kw in f for kw in ("roe", "pe", "pb", "eps", "profit", "revenue", "growth")):
            return "quality"
        if any(kw in f for kw in ("corr", "beta", "capm", "regress")):
            return "risk"
        if any(kw in f for kw in ("value", "bv", "cf", "dividend")):
            return "value"
        return "momentum"  # default


@register_node
class SaveAsTemplateNode(BaseNode):
    """Save current workflow as a reusable template.

    Serialises the current workflow DAG (nodes + edges + config) into the
    template registry so it can be instantiated later from the Projects page
    or the marketplace.

    Inputs:
      - strategy_code/PARAMS (required): Strategy code from Agent/Strategy
      - backtest_result/BACKTEST_RESULT (optional): Performance snapshot

    Outputs:
      - template_result/PARAMS: {template_id, name, status}
    """
    node_type = "save_as_template"
    category = "output"
    label = "Save as Template"
    description = "Save current workflow as a reusable template for later projects"
    icon = "Download"
    resource_profile = "io_bound"

    inputs = [
        BaseNode.in_port("strategy_code", PortType.PARAMS,
                         description="Strategy code from upstream"),
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT, required=False,
                         description="Performance snapshot for the template"),
    ]
    outputs = [
        BaseNode.out_port("template_result", PortType.PARAMS,
                          description="Template save result"),
    ]
    config_schema = {
        "name": {
            "title": "Template Name", "type": "string", "default": "",
        },
        "description": {
            "title": "Description", "type": "string", "default": "",
        },
        "category": {
            "title": "Category", "type": "string",
            "enum": ["trend", "reversal", "grid", "arbitrage", "multiFactor"], "default": "trend", "inline": True,
        },
        "difficulty": {
            "title": "Difficulty", "type": "string",
            "enum": ["beginner", "intermediate", "advanced"], "default": "beginner", "inline": True,
        },
        "publish_to_marketplace": {
            "title": "Publish", "type": "boolean", "default": False,
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        strategy_code = inputs.get("strategy_code", {})
        name = config.get("name", "") or f"Template_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}"
        description = config.get("description", "")
        category = config.get("category", "trend")
        difficulty = config.get("difficulty", "beginner")
        publish = config.get("publish_to_marketplace", False)

        try:
            from src.db.async_pool import async_get_connection

            async with async_get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO vt_strategy_marketplace
                       (name, description, code, category, tags, author, rating)
                       VALUES (%s, %s, %s, %s, %s, %s, 0)
                       RETURNING id""",
                    (name, description,
                     strategy_code.get("code", "") if isinstance(strategy_code, dict) else str(strategy_code),
                     category, f"{difficulty},template", "user"),
                )
                row = cur.fetchone()
                cur.close()
                template_id = str(row[0]) if row else "unknown"

            logger.info("Template saved: %s (id=%s)", name, template_id)

            result = {
                "template_id": template_id,
                "name": name,
                "status": "saved",
                "published": publish,
            }

            if publish:
                result["url"] = f"/marketplace/{template_id}"

            return {
                "template_result": result,
                "_summary": {"saved": name, "published": "yes" if publish else "no"},
            }

        except (ValueError, KeyError, RuntimeError, IOError) as e:
            logger.exception("SaveAsTemplate failed")
            return {
                "template_result": {"error": str(e), "status": "failed"},
                "_summary": {"error": str(e)[:40]},
            }
