/**
 * VisualizerNode — custom React Flow nodes for displaying backtest results.
 *
 * Three node types share common plumbing (header, ports, footer) but render
 * different content in the body:
 *   - equity_curve:   ECharts equity curve + drawdown chart
 *   - metrics_view:   KPI card grid
 *   - trades_view:    Trade history table
 */

import { memo, useEffect, useMemo, useRef } from "react";
import { Handle, NodeProps, Position } from "@xyflow/react";
import { cn } from "@/lib/utils";
import { echarts, CHART_GROUP, connectCharts } from "@/lib/echarts";
import { useDarkMode } from "@/hooks/useDarkMode";
import { abbreviateNum } from "@/lib/formatters";


// ── Shared header ────────────────────────────────────────────────────────

function VisualizerHeader({
  icon,
  label,
  status,
  nodeShortId,
}: {
  icon: string;
  label: string;
  status: string;
  nodeShortId: string;
}) {
  const statusDot: Record<string, string> = {
    done: "bg-green-500",
    error: "bg-red-500",
    running: "bg-blue-500 animate-pulse",
  };
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1.5 border-b bg-muted/20">
      <span className="text-[9px] text-muted-foreground font-mono shrink-0">{nodeShortId}</span>
      <span className="text-base shrink-0">{icon}</span>
      <span className="flex-1 text-xs font-medium truncate">{label}</span>
      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", statusDot[status] || "bg-muted-foreground")} />
    </div>
  );
}

// ── Port handles ──────────────────────────────────────────────────────────

function InputHandle() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      <Handle
        type="target"
        position={Position.Left}
        id="source"
        className="!w-[14px] !h-[14px] !border-[3px] !border-purple-400 !bg-purple-50 dark:!bg-purple-950 !rounded-full"
      />
      <span className="text-[10px] text-muted-foreground">回测</span>
    </div>
  );
}

function OutputHandle() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5 justify-end">
      <span className="text-[10px] text-muted-foreground">数据</span>
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        className="!w-[14px] !h-[14px] !border-[3px] !border-muted-foreground !bg-muted !rounded-full"
      />
    </div>
  );
}

// ── Shared footer ─────────────────────────────────────────────────────────

function VisualizerFooter({ status, durationMs, summary }: {
  status: string; durationMs?: number; summary?: Record<string, unknown>;
}) {
  if (status === "done" && summary) {
    const badge = formatSummary(summary);
    return (
      <div className="border-t border-green-200 dark:border-green-800 px-2 py-1 text-[10px] text-muted-foreground bg-green-50/30 dark:bg-green-950/20 flex items-center gap-1">
        <span className="text-green-500 shrink-0">✓</span>
        <span className="truncate" title={badge}>{badge}</span>
        {durationMs ? <span className="text-muted-foreground/50 ml-auto shrink-0">{durationMs}ms</span> : null}
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="border-t border-red-200 dark:border-red-800 px-2 py-1 text-[10px] text-down dark:text-down bg-red-50 dark:bg-red-950/30">
        ✗ Error
      </div>
    );
  }
  if (status === "running") {
    return (
      <div className="border-t border-blue-200 dark:border-blue-800 px-2 py-1 text-[10px] text-blue-500 bg-blue-50/30 dark:bg-blue-950/20 animate-pulse">
        ⏳ Running...
      </div>
    );
  }
  return null;
}

function formatSummary(s: Record<string, unknown>): string {
  const type = s.type as string;
  if (type === "equity_curve") {
    const parts: string[] = [];
    if (s.sharpe != null) parts.push(`Sharpe: ${Number(s.sharpe).toFixed(2)}`);
    if (s.total_return != null) parts.push(`Ret: ${(Number(s.total_return) * 100).toFixed(1)}%`);
    if (s.final_equity != null) parts.push(`Eq: ${abbreviateNum(Number(s.final_equity))}`);
    return parts.join(" · ") || "Equity curve";
  }
  if (type === "metrics") {
    const m = (s.metrics || {}) as Record<string, number>;
    const parts: string[] = [];
    if (m.sharpe != null) parts.push(`Sharpe: ${Number(m.sharpe).toFixed(2)}`);
    if (m.total_return != null) parts.push(`Ret: ${(Number(m.total_return) * 100).toFixed(1)}%`);
    if (m.max_drawdown != null) parts.push(`DD: ${(Number(m.max_drawdown) * 100).toFixed(1)}%`);
    return parts.join(" · ") || "Metrics";
  }
  if (type === "trades") {
    const count = s.trade_count || ((s.trades as any[])?.length || 0);
    return `${count} trades`;
  }
  return "Done";
}

// ═══════════════════════════════════════════════════════════════════════════
//  1. Equity Curve Node — ECharts line chart
// ═══════════════════════════════════════════════════════════════════════════

const EquityCurveVisualNode = memo(function EquityCurveVisualNode({ data, selected }: NodeProps) {
  const d = data as Record<string, unknown>;
  const summary = (d.summary || {}) as Record<string, unknown>;
  const status = (d.status as string) || "pending";
  const label = (d.label as string) || "Equity Curve";
  const durationMs = d.duration_ms as number | undefined;
  const nodeShortId = `#${(d.id as string || "").slice(0, 4)}`;

  const hasData = status === "done" && summary.type === "equity_curve" && Array.isArray(summary.equity_curve) && summary.equity_curve.length > 0;

  return (
    <div className={cn(
      "rounded-lg border-2 bg-card shadow-sm w-[480px] transition-colors",
      selected && "border-primary ring-2 ring-primary/20",
      status === "done" && "border-green-500 bg-green-50/30 dark:bg-green-950/20",
      status === "error" && "border-red-500 bg-red-50/30 dark:bg-red-950/30",
      status === "running" && "border-blue-500 bg-blue-50/30 dark:bg-blue-950/20 animate-pulse",
    )}>
      <VisualizerHeader icon="📈" label={label} status={status} nodeShortId={nodeShortId} />

      <div className="px-1 py-1">
        <InputHandle />
        <OutputHandle />
      </div>

      {hasData ? (
        <EquityCurveChart data={summary as unknown as EquityCurveSummary} />
      ) : status === "error" ? (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Error loading equity curve</div>
      ) : status === "running" ? (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Computing...</div>
      ) : (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Run workflow to display equity curve</div>
      )}

      <VisualizerFooter status={status} durationMs={durationMs} summary={summary} />
    </div>
  );
});

interface EquityCurveSummary {
  equity_curve: { time: string; equity: number }[];
  final_equity: number;
  max_drawdown: number;
  total_return: number;
  sharpe: number;
}

function EquityCurveChart({ data }: { data: EquityCurveSummary }) {
  const ref = useRef<HTMLDivElement>(null);
  const { dark } = useDarkMode();

  const points = data.equity_curve || [];

  // Compute drawdown from equity curve
  const chartData = useMemo(() => {
    let peak = -Infinity;
    return points.map((p) => {
      if (p.equity > peak) peak = p.equity;
      const dd = peak > 0 ? (p.equity - peak) / peak : 0;
      return { ...p, drawdown: dd };
    });
  }, [points]);

  useEffect(() => {
    if (!ref.current || chartData.length === 0) return;
    const isDark = dark;
    const textColor = isDark ? "#94a3b8" : "#64748b";
    const borderColor = isDark ? "#334155" : "#e2e8f0";
    const chart = echarts.init(ref.current);
    chart.group = CHART_GROUP;
    connectCharts();

    const dates = chartData.map((d) => d.time);
    const equity = chartData.map((d) => d.equity);
    const dd = chartData.map((d) => Number((d.drawdown * 100).toFixed(2)));

    chart.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      legend: { data: ["权益", "回撤%"], top: 4, textStyle: { fontSize: 10, color: textColor } },
      grid: { left: 60, right: 50, top: 30, bottom: 15 },
      xAxis: { type: "category", data: dates, axisLabel: { fontSize: 9, color: textColor, hideOverlap: true } },
      yAxis: [
        { type: "value", axisLabel: { fontSize: 9, color: textColor, formatter: (v: number) => abbreviateNum(v) }, splitLine: { lineStyle: { color: borderColor } } },
        { type: "value", inverse: true, axisLabel: { fontSize: 9, color: textColor, formatter: (v: number) => v + "%" }, splitLine: { show: false } },
      ],
      series: [
        {
          type: "line", name: "权益", data: equity, yAxisIndex: 0, smooth: true,
          lineStyle: { color: "#3b82f6", width: 2 },
          areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "#3b82f640" }, { offset: 1, color: "#3b82f605" }] } },
          symbol: "none",
        },
        {
          type: "line", name: "回撤%", data: dd, yAxisIndex: 1,
          lineStyle: { color: "#ef4444", width: 1, type: "dashed" },
          areaStyle: { color: "#ef444420" }, symbol: "none",
        },
      ],
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.dispose(); };
  }, [chartData, dark]);

  return (
    <div>
      <div className="flex items-center gap-3 px-3 py-1 text-[10px] text-muted-foreground border-b">
        <span>最终权益: <span className="font-mono font-semibold text-foreground">{abbreviateNum(data.final_equity)}</span></span>
        <span className="text-down">最大回撤: <span className="font-mono font-semibold">{(data.max_drawdown * 100).toFixed(1)}%</span></span>
      </div>
      <div ref={ref} style={{ height: 260, width: "100%" }} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//  2. Metrics View Node — KPI card grid
// ═══════════════════════════════════════════════════════════════════════════

const MetricsCardVisualNode = memo(function MetricsCardVisualNode({ data, selected }: NodeProps) {
  const d = data as Record<string, unknown>;
  const summary = (d.summary || {}) as Record<string, unknown>;
  const status = (d.status as string) || "pending";
  const label = (d.label as string) || "Metrics";
  const durationMs = d.duration_ms as number | undefined;
  const nodeShortId = `#${(d.id as string || "").slice(0, 4)}`;

  const metrics = (summary.type === "metrics" ? (summary.metrics || {}) : {}) as Record<string, number>;
  const hasData = status === "done" && Object.keys(metrics).length > 0;

  return (
    <div className={cn(
      "rounded-lg border-2 bg-card shadow-sm w-[460px] transition-colors",
      selected && "border-primary ring-2 ring-primary/20",
      status === "done" && "border-green-500 bg-green-50/30 dark:bg-green-950/20",
      status === "error" && "border-red-500 bg-red-50/30 dark:bg-red-950/30",
      status === "running" && "border-blue-500 bg-blue-50/30 dark:bg-blue-950/20 animate-pulse",
    )}>
      <VisualizerHeader icon="📊" label={label} status={status} nodeShortId={nodeShortId} />

      <div className="px-1 py-1">
        <InputHandle />
        <OutputHandle />
      </div>

      {hasData ? (
        <MetricsGrid metrics={metrics} />
      ) : status === "error" ? (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Error loading metrics</div>
      ) : status === "running" ? (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Computing...</div>
      ) : (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Run workflow to display metrics</div>
      )}

      <VisualizerFooter status={status} durationMs={durationMs} summary={summary} />
    </div>
  );
});

const METRICS_ITEMS = [
  { key: "total_return", label: "总收益", fmt: (v: number) => (v * 100).toFixed(2) + "%", positive: true },
  { key: "annual_return", label: "年化收益", fmt: (v: number) => (v * 100).toFixed(2) + "%", positive: true },
  { key: "sharpe", label: "夏普比率", fmt: (v: number) => v.toFixed(3), positive: true },
  { key: "sortino", label: "索提诺", fmt: (v: number) => v.toFixed(3), positive: true },
  { key: "calmar", label: "卡玛比率", fmt: (v: number) => v.toFixed(3), positive: true },
  { key: "max_drawdown", label: "最大回撤", fmt: (v: number) => (v * 100).toFixed(2) + "%", positive: false },
  { key: "win_rate", label: "胜率", fmt: (v: number) => (v * 100).toFixed(1) + "%", positive: true },
  { key: "trade_count", label: "交易次数", fmt: (v: number) => String(Math.round(v)), positive: true },
  { key: "profit_factor", label: "盈亏因子", fmt: (v: number) => v.toFixed(2), positive: true },
  { key: "profit_loss_ratio", label: "盈亏比", fmt: (v: number) => v.toFixed(2), positive: true },
  { key: "avg_holding_days", label: "平均持仓(天)", fmt: (v: number) => v.toFixed(1), positive: true },
  { key: "beta", label: "Beta", fmt: (v: number) => v.toFixed(3), positive: false },
  { key: "excess_return", label: "超额收益", fmt: (v: number) => (v * 100).toFixed(2) + "%", positive: true },
  { key: "information_ratio", label: "信息比率", fmt: (v: number) => v.toFixed(3), positive: true },
  { key: "final_value", label: "最终权益", fmt: (v: number) => v.toLocaleString(), positive: true },
];

function MetricsGrid({ metrics }: { metrics: Record<string, number> }) {
  const items = METRICS_ITEMS.filter((item) => metrics[item.key] !== undefined);
  if (items.length === 0) {
    return <div className="px-3 py-6 text-xs text-muted-foreground text-center">No metrics available</div>;
  }
  return (
    <div className="grid grid-cols-3 gap-2 p-3">
      {items.map((item) => {
        const val = metrics[item.key];
        const isGood = item.positive ? val >= 0 : val <= 0;
        return (
          <div key={item.key} className="text-center p-2 rounded-lg bg-muted/30 border border-border/30">
            <div className="text-[9px] text-muted-foreground mb-0.5">{item.label}</div>
            <div className={cn("text-xs font-bold tabular-nums", isGood ? "text-up" : "text-down")}>
              {item.fmt(val)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//  3. Trades View Node — trade history table
// ═══════════════════════════════════════════════════════════════════════════

const TradesTableVisualNode = memo(function TradesTableVisualNode({ data, selected }: NodeProps) {
  const d = data as Record<string, unknown>;
  const summary = (d.summary || {}) as Record<string, unknown>;
  const status = (d.status as string) || "pending";
  const label = (d.label as string) || "Trades";
  const durationMs = d.duration_ms as number | undefined;
  const nodeShortId = `#${(d.id as string || "").slice(0, 4)}`;

  const trades = (summary.type === "trades" ? (summary.trades || []) : []) as TradeRecord[];
  const hasData = status === "done" && trades.length > 0;

  return (
    <div className={cn(
      "rounded-lg border-2 bg-card shadow-sm w-[520px] transition-colors",
      selected && "border-primary ring-2 ring-primary/20",
      status === "done" && "border-green-500 bg-green-50/30 dark:bg-green-950/20",
      status === "error" && "border-red-500 bg-red-50/30 dark:bg-red-950/30",
      status === "running" && "border-blue-500 bg-blue-50/30 dark:bg-blue-950/20 animate-pulse",
    )}>
      <VisualizerHeader icon="📋" label={label} status={status} nodeShortId={nodeShortId} />

      <div className="px-1 py-1">
        <InputHandle />
        <OutputHandle />
      </div>

      {hasData ? (
        <TradesTable trades={trades} />
      ) : status === "error" ? (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Error loading trades</div>
      ) : status === "running" ? (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Computing...</div>
      ) : (
        <div className="px-3 py-8 text-xs text-muted-foreground text-center">Run workflow to display trades</div>
      )}

      <VisualizerFooter status={status} durationMs={durationMs} summary={summary} />
    </div>
  );
});

interface TradeRecord {
  code: string;
  side: string;
  time: string;
  price: number;
  reason: string;
  pnl?: number;
}

function TradesTable({ trades }: { trades: TradeRecord[] }) {
  // Show trades in pairs: entry then exit
  const rows = trades.slice(0, 100); // limit display
  if (rows.length === 0) {
    return <div className="px-3 py-6 text-xs text-muted-foreground text-center">No trade records</div>;
  }

  return (
    <div className="max-h-[280px] overflow-y-auto">
      <table className="w-full text-[10px]">
        <thead>
          <tr className="border-b bg-muted/30 text-muted-foreground sticky top-0">
            <th className="px-2 py-1 text-left font-medium w-[80px]">代码</th>
            <th className="px-2 py-1 text-left font-medium w-[44px]">方向</th>
            <th className="px-2 py-1 text-right font-medium w-[60px]">价格</th>
            <th className="px-2 py-1 text-left font-medium">时间</th>
            <th className="px-2 py-1 text-left font-medium w-[70px]">原因</th>
            <th className="px-2 py-1 text-right font-medium w-[60px]">PnL</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((tr, i) => (
            <tr key={i} className="border-b border-border/30 hover:bg-muted/20">
              <td className="px-2 py-1 font-mono">{tr.code?.replace(/\.(SZ|SH)$/, "")}</td>
              <td className={cn("px-2 py-1 font-medium", tr.side === "BUY" ? "text-down" : "text-up")}>
                {tr.side === "BUY" ? "买" : "卖"}
              </td>
              <td className="px-2 py-1 text-right font-mono">{tr.price?.toFixed(2)}</td>
              <td className="px-2 py-1 text-muted-foreground font-mono">{tr.time?.slice(0, 10)}</td>
              <td className="px-2 py-1 text-muted-foreground">{tr.reason || "—"}</td>
              <td className={cn("px-2 py-1 text-right font-mono", (tr.pnl || 0) >= 0 ? "text-up" : "text-down")}>
                {tr.pnl != null ? (tr.pnl >= 0 ? "+" : "") + tr.pnl.toFixed(0) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Exports for ReactFlow nodeTypes map ─────────────────────────────────

export const visualizerNodeTypes = {
  equity_curve: EquityCurveVisualNode,
  metrics_view: MetricsCardVisualNode,
  trades_view: TradesTableVisualNode,
};
