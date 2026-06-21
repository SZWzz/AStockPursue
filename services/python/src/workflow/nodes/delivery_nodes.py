"""Delivery nodes — PDF reports and multi-strategy portfolio combining.

These nodes handle final delivery of workflow results:
- PDFReportNode: renders a professional PDF report from backtest results via Jinja2 + WeasyPrint
- PortfolioNode: combines signals from up to 5 strategies into a single portfolio
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.workflow.node_base import BaseNode
from src.workflow.node_registry import register_node
from src.workflow.schema import PortType

logger = logging.getLogger(__name__)

# ── Built-in PDF templates ────────────────────────────────────────────────────

_DEFAULT_PDF_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: Helvetica, Arial, sans-serif; color: #222; font-size: 11pt; line-height: 1.5; }
  h1 { color: #1a365d; border-bottom: 2px solid #2b6cb0; padding-bottom: 8px; font-size: 22pt; }
  h2 { color: #2b6cb0; margin-top: 24px; font-size: 14pt; }
  .meta { color: #666; font-size: 9pt; margin-bottom: 24px; }
  table { border-collapse: collapse; width: 100%%; margin: 12px 0; }
  th, td { border: 1px solid #cbd5e0; padding: 6px 10px; text-align: left; font-size: 10pt; }
  th { background: #ebf4ff; font-weight: 600; }
  .positive { color: #276749; }
  .negative { color: #c53030; }
  .chart-placeholder { border: 1px dashed #a0aec0; padding: 40px; text-align: center; color: #718096;
                       margin: 16px 0; border-radius: 4px; background: #f7fafc; }
  .footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid #e2e8f0;
            font-size: 8pt; color: #a0aec0; text-align: center; }
</style>
</head>
<body>
<h1>{{ title }}</h1>
<div class="meta">
  Author: {{ author }} &mdash; Generated: {{ generated_at }} &mdash; Template: {{ template_name }}
</div>

<h2>Performance Metrics</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  {% for key, val in metrics.items() %}
  <tr><td>{{ key }}</td><td>{{ val }}</td></tr>
  {% endfor %}
</table>

{% if include_charts %}
<h2>Equity Curve</h2>
<div class="chart-placeholder">
  [Equity curve — {{ equity_points }} data points]<br>
  <em>Render in frontend or export as PNG for production reports</em>
</div>
{% endif %}

<h2>Trade Summary</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  {% for key, val in trade_summary.items() %}
  <tr><td>{{ key }}</td><td>{{ val }}</td></tr>
  {% endfor %}
</table>

<h2>Risk Metrics</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  {% for key, val in risk_metrics.items() %}
  <tr><td>{{ key }}</td><td>{{ val }}</td></tr>
  {% endfor %}
</table>

<div class="footer">
  AStockPursue &mdash; Automated Report &bull; {{ generated_at }}
</div>
</body>
</html>
"""

_COMPACT_PDF_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 1.5cm; }
  body { font-family: Helvetica, Arial, sans-serif; color: #222; font-size: 10pt; }
  h1 { font-size: 18pt; margin-bottom: 4px; }
  .meta { color: #888; font-size: 8pt; margin-bottom: 16px; }
  table { border-collapse: collapse; width: 100%%; margin: 8px 0; }
  th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left; font-size: 9pt; }
  th { background: #f0f4f8; }
</style>
</head>
<body>
<h1>{{ title }}</h1>
<div class="meta">{{ author }} | {{ generated_at }}</div>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  {% for key, val in metrics.items() %}
  <tr><td>{{ key }}</td><td>{{ val }}</td></tr>
  {% endfor %}
</table>
</body>
</html>
"""


# ── PDF Report Node ───────────────────────────────────────────────────────────

@register_node
class PDFReportNode(BaseNode):
    """Generate a professional PDF report from backtest results.

    Renders Jinja2 HTML templates with performance metrics, equity curve
    placeholder, trade summary, and risk metrics, then converts to PDF
    via WeasyPrint.  Output is saved under runs/{run_id}/reports/.
    """
    node_type = "pdf_report"
    category = "output"
    label = "PDF Report"
    description = (
        "Generate a professional PDF report from backtest results using "
        "Jinja2 templates and WeasyPrint. Includes metrics tables, equity "
        "curve placeholder, trade summary, and risk metrics."
    )
    icon = "FileText"
    resource_profile = "io_bound"

    inputs = [
        BaseNode.in_port("backtest_result", PortType.BACKTEST_RESULT,
                         description="Backtest result with metrics, equity curve, trades"),
        BaseNode.in_port("params", PortType.PARAMS, required=False,
                         description="Optional overrides: title, author, template"),
    ]
    outputs = [
        BaseNode.out_port("report", PortType.PARAMS,
                          description="PDF report metadata: pdf_path, pdf_url, page_count"),
    ]
    config_schema = {
        "title": {
            "title": "Report Title", "type": "string",
            "default": "Quantitative Backtest Report",
        },
        "author": {
            "title": "Author", "type": "string", "default": "AStockPursue",
        },
        "template": {
            "title": "Template", "type": "string",
            "enum": ["default", "compact", "detailed"], "default": "default",
        },
        "include_charts": {
            "title": "Include Charts", "type": "boolean", "default": True,
            "description": "Include equity curve placeholder in the report",
        },
        "output_dir": {
            "title": "Output Directory", "type": "string", "default": "",
            "description": "Override output directory. Empty = auto (runs/{run_id}/reports/).",
        },
        "template_content": {
            "title": "Custom Template (Jinja2)", "type": "string", "default": "",
            "description": "Override built-in template with custom Jinja2 HTML. Available variables: title, author, generated_at, template_name, metrics, include_charts, equity_points, trade_summary, risk_metrics. Leave empty to use built-in template.",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        bt = inputs.get("backtest_result", {})
        if not bt or not isinstance(bt, dict):
            return {"report": {"error": "No backtest result provided"}}

        params_override = inputs.get("params", {}) if isinstance(inputs.get("params"), dict) else {}

        title = config.get("title", "") or params_override.get("title", "Quantitative Backtest Report")
        author = config.get("author", "") or params_override.get("author", "AStockPursue")
        template_name = config.get("template", "default")
        include_charts = config.get("include_charts", True)
        output_dir = config.get("output_dir", "").strip()

        # ── Extract data from backtest result ─────────────────────────────
        metrics = bt.get("metrics", bt.get("summary", {}))
        if isinstance(metrics, dict):
            metrics = {k: v for k, v in metrics.items() if v is not None}
        else:
            metrics = {}

        equity_curve = bt.get("equity_curve") or bt.get("equity")
        equity_points = 0
        if isinstance(equity_curve, list):
            equity_points = len(equity_curve)

        trades = bt.get("trades", bt.get("trade_markers", []))
        trade_summary = self._build_trade_summary(trades, metrics)
        risk_metrics = self._build_risk_metrics(metrics)

        # ── Render HTML ───────────────────────────────────────────────────
        try:
            from jinja2 import Environment, BaseLoader
            env = Environment(loader=BaseLoader(), autoescape=True)

            template_str = config.get("template_content", "").strip()
            if not template_str:
                template_str = _DEFAULT_PDF_TEMPLATE
                if template_name == "compact":
                    template_str = _COMPACT_PDF_TEMPLATE
                # "detailed" uses the default template with charts enabled
                if template_name == "detailed":
                    include_charts = True

            tmpl = env.from_string(template_str)
            html = tmpl.render(
                title=title,
                author=author,
                generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                template_name=template_name,
                metrics=metrics,
                include_charts=include_charts,
                equity_points=equity_points,
                trade_summary=trade_summary,
                risk_metrics=risk_metrics,
            )
        except ImportError:
            return {"report": {"error": "jinja2 not installed - pip install jinja2"}}
        except Exception as e:
            logger.exception("PDF template render failed")
            return {"report": {"error": f"Template render error: {e}"}}

        # ── Convert to PDF via WeasyPrint ─────────────────────────────────
        try:
            from weasyprint import HTML as WeasyHTML
        except ImportError:
            return {"report": {"error": "weasyprint not installed - pip install weasyprint"}}

        # ── Resolve output path ───────────────────────────────────────────
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:40]).strip("_")
        filename = f"{safe_title}_{ts}.pdf"

        if output_dir:
            out_path = Path(output_dir)
        else:
            out_path = Path("backend/runs/_pending/reports")

        out_path.mkdir(parents=True, exist_ok=True)
        pdf_path = out_path / filename

        try:
            WeasyHTML(string=html).write_pdf(str(pdf_path))
        except Exception as e:
            logger.exception("WeasyPrint PDF generation failed")
            return {"report": {"error": f"PDF generation failed: {e}"}}

        page_count = 0
        try:
            doc = WeasyHTML(string=html).render()
            page_count = len(doc.pages)
        except Exception:
            pass

        pdf_size = pdf_path.stat().st_size if pdf_path.exists() else 0
        pdf_url = f"/reports/{filename}"

        logger.info("PDFReport: %s (%d bytes, %d pages)", pdf_path, pdf_size, page_count)

        return {
            "report": {
                "pdf_path": str(pdf_path),
                "pdf_url": pdf_url,
                "filename": filename,
                "page_count": page_count,
                "size_bytes": pdf_size,
                "title": title,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def _build_trade_summary(trades: list, metrics: dict) -> dict:
        summary: Dict[str, Any] = {}
        if isinstance(trades, list) and trades:
            summary["Total Trades"] = len(trades)
            buys = sum(1 for t in trades if str(t.get("side", "")).upper() == "BUY")
            sells = len(trades) - buys
            summary["Buy Entries"] = buys
            summary["Sell Entries"] = sells
        if "trade_count" in metrics:
            summary["Trade Count"] = metrics["trade_count"]
        if "win_rate" in metrics:
            wr = metrics["win_rate"]
            summary["Win Rate"] = f"{wr:.2%}" if isinstance(wr, (int, float)) else wr
        if "profit_factor" in metrics:
            summary["Profit Factor"] = metrics["profit_factor"]
        if not summary:
            summary["Note"] = "No trade data available"
        return summary

    @staticmethod
    def _build_risk_metrics(metrics: dict) -> dict:
        risk: Dict[str, Any] = {}
        for key in ("max_drawdown", "volatility", "sharpe", "sortino", "calmar"):
            if key in metrics and metrics[key] is not None:
                risk[key] = metrics[key]
        if "annual_return" in metrics:
            risk["Annual Return"] = metrics["annual_return"]
        if "total_return" in metrics:
            risk["Total Return"] = metrics["total_return"]
        if not risk:
            risk["Note"] = "No risk data available"
        return risk


# ── Portfolio Combiner Node ───────────────────────────────────────────────────

@register_node
class PortfolioNode(BaseNode):
    """Combine multiple strategy signals into a single portfolio signal.

    Accepts up to 5 strategy signal inputs, aligns their timestamps, and
    applies an allocation method (equal weight, risk parity, min variance,
    or max Sharpe) to produce a unified portfolio signal.
    """
    node_type = "portfolio_combiner"
    category = "strategy"
    label = "Portfolio Combiner"
    description = (
        "Combine multiple strategy signals into a portfolio with allocation "
        "optimization. Supports equal weight, risk parity, min variance, and "
        "max Sharpe methods."
    )
    icon = "PieChart"

    inputs = [
        BaseNode.in_port("signal_1", PortType.SIGNAL, required=True,
                         description="Strategy 1 signal"),
        BaseNode.in_port("signal_2", PortType.SIGNAL, required=False,
                         description="Strategy 2 signal"),
        BaseNode.in_port("signal_3", PortType.SIGNAL, required=False,
                         description="Strategy 3 signal"),
        BaseNode.in_port("signal_4", PortType.SIGNAL, required=False,
                         description="Strategy 4 signal"),
        BaseNode.in_port("signal_5", PortType.SIGNAL, required=False,
                         description="Strategy 5 signal"),
        BaseNode.in_port("backtest_results", PortType.BACKTEST_RESULT, required=False,
                         description="Optional backtest results for risk-parity / optimization"),
    ]
    outputs = [
        BaseNode.out_port("signal", PortType.PORTFOLIO_SIGNAL,
                          description="Combined portfolio signal (compatible with SIGNAL port)"),
        BaseNode.out_port("backtest_result", PortType.BACKTEST_RESULT,
                          description="Portfolio-level metrics from the combined signal"),
    ]
    config_schema = {
        "method": {
            "title": "Allocation Method", "type": "string",
            "enum": ["equal_weight", "risk_parity", "min_variance", "max_sharpe"],
            "default": "equal_weight",
        },
        "rebalance_freq": {
            "title": "Rebalance Frequency", "type": "string",
            "enum": ["daily", "weekly", "monthly", "none"],
            "default": "daily",
            "description": "How often to recalculate weights",
        },
        "max_weight_per_strategy": {
            "title": "Max Weight Per Strategy", "type": "number",
            "default": 0.5, "minimum": 0.1, "maximum": 1.0,
            "description": "Maximum allocation weight for any single strategy",
        },
    }

    async def execute(self, inputs: dict, config: dict) -> dict:
        method = config.get("method", "equal_weight")
        rebalance_freq = config.get("rebalance_freq", "daily")
        max_weight = float(config.get("max_weight_per_strategy", 0.5))

        # ── Collect signals ───────────────────────────────────────────────
        signals: List[pd.DataFrame] = []
        for i in range(1, 6):
            sig = inputs.get(f"signal_{i}")
            if sig is not None:
                df = self._to_dataframe(sig)
                if df is not None and not df.empty:
                    signals.append(df)

        if not signals:
            return {
                "signal": {},
                "backtest_result": {"error": "No valid signals provided"},
            }

        n_strategies = len(signals)

        # ── Align timestamps ──────────────────────────────────────────────
        aligned = self._align_signals(signals)
        if aligned is None or len(aligned) == 0:
            return {
                "signal": {},
                "backtest_result": {"error": "Failed to align signal timestamps"},
            }

        # ── Compute weights ───────────────────────────────────────────────
        weights = self._compute_weights(
            aligned, method, n_strategies, max_weight, rebalance_freq,
        )

        # ── Combine into portfolio signal ─────────────────────────────────
        combined = self._combine_signals(aligned, weights)

        # ── Compute portfolio metrics ─────────────────────────────────────
        portfolio_metrics = self._compute_portfolio_metrics(combined)

        logger.info(
            "PortfolioCombiner: %d strategies, method=%s, %d bars",
            n_strategies, method, len(combined),
        )

        return {
            "signal": {"portfolio": combined, "method": method,
                        "n_strategies": n_strategies, "weights": weights.to_dict() if isinstance(weights, pd.DataFrame) else weights},
            "backtest_result": portfolio_metrics,
        }

    @staticmethod
    def _to_dataframe(sig) -> Optional[pd.DataFrame]:
        """Convert various signal formats to a DataFrame."""
        if isinstance(sig, pd.DataFrame):
            return sig
        if isinstance(sig, dict):
            if "portfolio" in sig and isinstance(sig["portfolio"], pd.DataFrame):
                return sig["portfolio"]
            try:
                return pd.DataFrame(sig)
            except Exception:
                return None
        if isinstance(sig, pd.Series):
            return sig.to_frame()
        return None

    @staticmethod
    def _align_signals(signals: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Outer-join align all signals on their index (timestamps)."""
        if not signals:
            return None
        result = signals[0].copy()
        for sig in signals[1:]:
            result = result.join(sig, how="outer", lsuffix="", rsuffix="_r")
        result = result.sort_index().ffill().fillna(0)
        return result

    def _compute_weights(
        self,
        aligned: pd.DataFrame,
        method: str,
        n_strategies: int,
        max_weight: float,
        rebalance_freq: str,
    ) -> pd.DataFrame:
        """Compute per-strategy weights over time."""
        n_cols = aligned.shape[1] if len(aligned.columns) > 0 else n_strategies

        if method == "equal_weight":
            w = 1.0 / max(n_cols, 1)
            weights = pd.DataFrame(
                w, index=aligned.index, columns=aligned.columns,
            )

        elif method == "risk_parity":
            weights = self._risk_parity_weights(aligned, max_weight)

        elif method == "min_variance":
            weights = self._min_variance_weights(aligned, max_weight)

        elif method == "max_sharpe":
            weights = self._max_sharpe_weights(aligned, max_weight)

        else:
            w = 1.0 / max(n_cols, 1)
            weights = pd.DataFrame(
                w, index=aligned.index, columns=aligned.columns,
            )

        # Apply rebalance mask
        if rebalance_freq != "none" and rebalance_freq != "daily":
            mask = self._rebalance_mask(aligned.index, rebalance_freq)
            weights = weights.where(mask, other=np.nan).ffill().fillna(weights.mean(axis=1), axis=0)

        # Enforce max weight cap
        weights = weights.clip(upper=max_weight)
        row_sums = weights.sum(axis=1).replace(0, 1)
        weights = weights.div(row_sums, axis=0)

        return weights

    @staticmethod
    def _risk_parity_weights(aligned: pd.DataFrame, max_weight: float) -> pd.DataFrame:
        """Inverse-volatility weighting (risk parity approximation)."""
        vols = aligned.rolling(window=20, min_periods=5).std()
        vols = vols.replace(0, np.nan).ffill().fillna(1.0)
        inv_vol = 1.0 / vols
        row_sums = inv_vol.sum(axis=1).replace(0, 1)
        weights = inv_vol.div(row_sums, axis=0)
        return weights.clip(upper=max_weight)

    @staticmethod
    def _min_variance_weights(aligned: pd.DataFrame, max_weight: float) -> pd.DataFrame:
        """Greedy minimum-variance approximation (rolling window)."""
        window = min(60, len(aligned))
        weights = pd.DataFrame(0.0, index=aligned.index, columns=aligned.columns)

        for end in range(window, len(aligned)):
            start = end - window
            chunk = aligned.iloc[start:end]
            cov = chunk.cov()
            if cov.empty:
                continue
            try:
                inv_diag = 1.0 / np.diag(cov.values)
                inv_diag = np.where(np.isfinite(inv_diag), inv_diag, 0)
                total = inv_diag.sum()
                if total > 0:
                    w = inv_diag / total
                else:
                    w = np.ones(len(aligned.columns)) / len(aligned.columns)
                w = np.clip(w, 0, max_weight)
                w = w / w.sum() if w.sum() > 0 else w
                weights.iloc[end] = w
            except Exception:
                weights.iloc[end] = 1.0 / len(aligned.columns)

        # Fill first window
        if window < len(aligned):
            first_w = weights.iloc[window]
            weights.iloc[:window] = first_w.values

        return weights

    @staticmethod
    def _max_sharpe_weights(aligned: pd.DataFrame, max_weight: float) -> pd.DataFrame:
        """Greedy maximum-Sharpe approximation."""
        window = min(60, len(aligned))
        weights = pd.DataFrame(0.0, index=aligned.index, columns=aligned.columns)

        for end in range(window, len(aligned)):
            start = end - window
            chunk = aligned.iloc[start:end]
            mean_ret = chunk.mean()
            std_ret = chunk.std().replace(0, np.nan)
            sharpe = (mean_ret / std_ret).fillna(0)
            sharpe_pos = sharpe.clip(lower=0)
            total = sharpe_pos.sum()
            if total > 0:
                w = (sharpe_pos / total).values
            else:
                w = np.ones(len(aligned.columns)) / len(aligned.columns)
            w = np.clip(w, 0, max_weight)
            w = w / w.sum() if w.sum() > 0 else w
            weights.iloc[end] = w

        if window < len(aligned):
            first_w = weights.iloc[window]
            weights.iloc[:window] = first_w.values

        return weights

    @staticmethod
    def _rebalance_mask(index: pd.DatetimeIndex, freq: str) -> pd.Series:
        """Return a boolean Series marking rebalance dates."""
        mask = pd.Series(False, index=index)
        if freq == "weekly":
            # First trading day of each week
            mask = mask.index.to_series().dt.isocalendar().week.ne(
                mask.index.to_series().dt.isocalendar().week.shift(1)
            )
        elif freq == "monthly":
            mask = mask.index.to_series().dt.month.ne(
                mask.index.to_series().dt.month.shift(1)
            )
        else:
            mask = pd.Series(True, index=index)
        return mask

    @staticmethod
    def _combine_signals(aligned: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
        """Weighted sum of strategy signals to produce portfolio signal."""
        combined = (aligned * weights).sum(axis=1)
        return combined.to_frame(name="portfolio_signal")

    @staticmethod
    def _compute_portfolio_metrics(combined: pd.DataFrame) -> dict:
        """Compute basic performance metrics from the combined signal."""
        if combined.empty:
            return {}

        s = combined.iloc[:, 0] if isinstance(combined, pd.DataFrame) else combined
        returns = s.dropna()

        if len(returns) < 2:
            return {"error": "Insufficient data for metrics"}

        total_return = float(returns.iloc[-1] / returns.iloc[0] - 1) if returns.iloc[0] != 0 else 0.0
        n_periods = len(returns)
        annual_factor = 252 / max(n_periods, 1)
        annual_return = float((1 + total_return) ** annual_factor - 1) if total_return > -1 else -1.0

        vol = float(returns.std() * math.sqrt(252)) if len(returns) > 1 else 0.0
        sharpe = float(annual_return / vol) if vol > 0 else 0.0

        # Max drawdown
        cum = (1 + returns).cumprod()
        peak = cum.cummax()
        drawdown = ((cum - peak) / peak).fillna(0)
        max_dd = float(drawdown.min())

        # Win rate
        positive = (returns > 0).sum()
        win_rate = float(positive / len(returns)) if len(returns) > 0 else 0.0

        return {
            "total_return": round(total_return, 6),
            "annual_return": round(annual_return, 6),
            "volatility": round(vol, 6),
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(max_dd, 6),
            "win_rate": round(win_rate, 4),
            "n_periods": n_periods,
        }
