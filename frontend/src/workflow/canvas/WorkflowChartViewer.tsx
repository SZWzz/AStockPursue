/**
 * WorkflowChartViewer — renders chart_payload from ChartDataNode as ECharts.
 * Tabs: K-line | Equity | Trades. Compact, scrollable, i18n-aware.
 */

import { useEffect, useRef, useState, useMemo } from "react";
import { echarts, CHART_GROUP, connectCharts } from "@/lib/echarts";
import { useI18n } from "@/lib/i18n";
import { abbreviateNum } from "@/lib/formatters";
import { calcMA } from "@/lib/indicators";
import { useDarkMode } from "@/hooks/useDarkMode";
import { HeatmapChart, type HeatmapData } from "@/components/charts/HeatmapChart";

interface ChartPayload {
  charts?: {
    candlestick?: { codes: string[]; series: Record<string, any[]> };
    equity?: { type: string; points: { time: string; equity: number; drawdown: number }[]; final_equity: number; max_drawdown: number };
    trades?: { code: string; side: string; time: string; price: number; reason: string }[];
    metrics?: { type: string; metrics: Record<string, number> };
    heatmap?: HeatmapData;
  };
}

interface Props { payload: ChartPayload }

const MA_COLORS = ["#f59e0b", "#8b5cf6", "#3b82f6", "#ec4899"];

export default function WorkflowChartViewer({ payload }: Props) {
  const { t } = useI18n();
  const charts = payload?.charts;

  // Hooks first — before any early return (React rules)
  const [codeIdx, setCodeIdx] = useState(0);
  const hasHeatmap = !!charts?.heatmap;
  const defaultTab = hasHeatmap ? ("heatmap" as const) : ("kline" as const);
  const [tab, setTab] = useState<"kline" | "equity" | "trades" | "metrics" | "heatmap">(defaultTab);

  if (!charts) return <p className="text-xs text-muted-foreground p-4">No chart data</p>;

  const codes = charts.candlestick?.codes || [];

  const tabs = [
    ...(hasHeatmap ? [{ key: "heatmap" as const, label: "热力图" }] : []),
    { key: "kline" as const, label: (t as any).tradingKline || "K线" },
    { key: "equity" as const, label: (t as any).ptEquity || "权益" },
    { key: "trades" as const, label: (t as any).trades || "交易" },
    { key: "metrics" as const, label: (t as any).metricsPanel || "指标" },
  ];

  return (
    <div className="flex flex-col" style={{ height: "380px" }}>
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-3 py-1.5 border-b bg-muted/30 shrink-0">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={`text-xs px-2.5 py-1 rounded transition-colors ${
              tab === tb.key ? "bg-background text-foreground font-medium shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tb.label}
          </button>
        ))}
        <div className="flex-1" />
        {tab === "kline" && codes.length > 0 && (
          <select value={codeIdx} onChange={(e) => setCodeIdx(+e.target.value)}
            className="text-xs px-2 py-0.5 rounded border bg-background max-w-[140px]">
            {codes.map((c, i) => (<option key={c} value={i}>{c}</option>))}
          </select>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === "heatmap" && charts.heatmap && (
          <div className="p-3">
            <HeatmapChart data={charts.heatmap} width={600} height={420} />
          </div>
        )}
        {tab === "kline" && charts.candlestick && (
          <KlineChart codes={codes} series={charts.candlestick.series} codeIdx={codeIdx} setCodeIdx={setCodeIdx}
            trades={charts.trades} />
        )}
        {tab === "equity" && charts.equity && (
          <EquityPanel data={charts.equity} />
        )}
        {tab === "trades" && (
          <TradePanel trades={charts.trades} />
        )}
        {tab === "metrics" && charts.metrics && (
          <MetricsPanel data={charts.metrics} />
        )}
      </div>
    </div>
  );
}

// ── K-line ────────────────────────────────────────────────────────────────

function KlineChart({ codes, series, codeIdx, setCodeIdx, trades }: any) {
  const ref = useRef<HTMLDivElement>(null);
  const dark = useDarkMode().dark;
  const code = codes[codeIdx] || "";
  const bars = useMemo(() => series[code] || [], [code, series]);
  const filteredTrades = useMemo(() => (trades || []).filter((t: any) => t.code === code), [trades, code]);

  useEffect(() => {
    if (!ref.current || bars.length === 0) return;
    const isDark = dark;
    const textColor = isDark ? "#94a3b8" : "#64748b";
    const borderColor = isDark ? "#334155" : "#e2e8f0";
    const chart = echarts.init(ref.current);
    chart.group = CHART_GROUP;
    connectCharts();

    const dates = bars.map((b: any) => b.time);
    const ohlc = bars.map((b: any) => [b.open, b.close, b.low, b.high]);
    const vols = bars.map((b: any) => b.volume);
    const closes = bars.map((b: any) => b.close);
    const ma5 = calcMA(closes, 5);
    const ma10 = calcMA(closes, 10);

    const markers: any[] = [];
    if (filteredTrades.length > 0) {
      for (const tr of filteredTrades) {
        const idx = dates.indexOf(tr.time);
        if (idx >= 0) {
          markers.push({
            coord: [idx, tr.side === "BUY" ? bars[idx].low * 0.995 : bars[idx].high * 1.005],
            value: tr.side === "BUY" ? "B" : "S",
            symbol: "pin", symbolSize: 18,
            itemStyle: { color: tr.side === "BUY" ? "#ef4444" : "#22c55e" },
            label: { show: true, fontSize: 8, color: "#fff" },
          });
        }
      }
    }

    chart.setOption({
      backgroundColor: "transparent",
      grid: [
        { left: 55, right: 15, top: 20, height: "50%" },
        { left: 55, right: 15, top: "73%", height: "22%" },
      ],
      xAxis: [
        { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
        { type: "category", data: dates, gridIndex: 1, axisLabel: { rotate: 0, fontSize: 9, color: textColor, interval: Math.max(1, Math.floor(dates.length / 12)) } },
      ],
      yAxis: [
        { type: "value", gridIndex: 0, scale: true, axisLabel: { fontSize: 9, color: textColor }, splitLine: { lineStyle: { color: borderColor } } },
        { type: "value", gridIndex: 1, splitLine: { show: false }, axisLabel: { fontSize: 8, color: textColor, formatter: (v: number) => abbreviateNum(v) } },
      ],
      series: [
        { type: "candlestick", data: ohlc, xAxisIndex: 0, yAxisIndex: 0, itemStyle: { color: "#ef4444", color0: "#22c55e", borderColor: "#ef4444", borderColor0: "#22c55e" }, markPoint: markers.length > 0 ? { data: markers } : undefined },
        { type: "line", name: "MA5", data: ma5, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1, color: MA_COLORS[0] }, symbol: "none" },
        { type: "line", name: "MA10", data: ma10, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1, color: MA_COLORS[1] }, symbol: "none" },
        { type: "bar", name: "VOL", data: vols, xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: isDark ? "#47556966" : "#94a3b866" }, barWidth: "60%" },
      ],
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.dispose(); };
  }, [bars, filteredTrades, dark, code]);

  return (
    <div>
      <div className="flex items-center gap-0.5 px-2 py-1 flex-wrap">
        {codes.map((c: string, i: number) => (
          <button key={c} onClick={() => setCodeIdx(i)}
            className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${i === codeIdx ? "bg-primary/10 text-primary font-semibold" : "text-muted-foreground hover:bg-muted"}`}>
            {c.replace(/\.(SZ|SH)$/, "")}
          </button>
        ))}
      </div>
      <div ref={ref} style={{ height: 340, width: "100%" }} />
    </div>
  );
}

// ── Metrics ───────────────────────────────────────────────────────────────

function MetricsPanel({ data }: { data: { metrics: Record<string, number> } }) {
  const m = data.metrics || {};
  const items = [
    { key: "total_return", label: "总收益", fmt: (v: number) => (v * 100).toFixed(2) + "%" },
    { key: "annual_return", label: "年化收益", fmt: (v: number) => (v * 100).toFixed(2) + "%" },
    { key: "sharpe", label: "夏普比率", fmt: (v: number) => v.toFixed(3) },
    { key: "sortino", label: "索提诺", fmt: (v: number) => v.toFixed(3) },
    { key: "calmar", label: "卡玛比率", fmt: (v: number) => v.toFixed(3) },
    { key: "max_drawdown", label: "最大回撤", fmt: (v: number) => (v * 100).toFixed(2) + "%" },
    { key: "win_rate", label: "胜率", fmt: (v: number) => (v * 100).toFixed(1) + "%" },
    { key: "trade_count", label: "交易次数", fmt: (v: number) => String(Math.round(v)) },
    { key: "profit_factor", label: "盈亏因子", fmt: (v: number) => v.toFixed(2) },
    { key: "profit_loss_ratio", label: "盈亏比", fmt: (v: number) => v.toFixed(2) },
    { key: "avg_holding_days", label: "平均持仓(天)", fmt: (v: number) => v.toFixed(1) },
    { key: "beta", label: "Beta", fmt: (v: number) => v.toFixed(3) },
    { key: "excess_return", label: "超额收益", fmt: (v: number) => (v * 100).toFixed(2) + "%" },
    { key: "information_ratio", label: "信息比率", fmt: (v: number) => v.toFixed(3) },
    { key: "final_value", label: "最终权益", fmt: (v: number) => v.toLocaleString() },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 p-3">
      {items.map((item) => {
        const val = m[item.key];
        if (val === undefined) return null;
        return (
          <div key={item.key} className="text-center p-2.5 rounded-lg bg-muted/30 border border-border/30">
            <div className="text-[10px] text-muted-foreground mb-0.5">{item.label}</div>
            <div className="text-sm font-bold tabular-nums text-foreground">{item.fmt(val)}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Equity ────────────────────────────────────────────────────────────────

function EquityPanel({ data }: { data: { points: { time: string; equity: number; drawdown: number }[]; final_equity: number; max_drawdown: number } }) {
  const ref = useRef<HTMLDivElement>(null);
  const { dark } = useDarkMode();

  useEffect(() => {
    if (!ref.current || !data.points?.length) return;
    const isDark = dark;
    const textColor = isDark ? "#94a3b8" : "#64748b";
    const borderColor = isDark ? "#334155" : "#e2e8f0";
    const chart = echarts.init(ref.current);
    chart.group = CHART_GROUP;
    connectCharts();

    const dates = data.points.map((d) => d.time);
    const equity = data.points.map((d) => d.equity);
    const dd = data.points.map((d) => Number((d.drawdown * 100).toFixed(2)));

    chart.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      legend: { data: ["权益", "回撤%"], top: 4, textStyle: { fontSize: 10, color: textColor } },
      grid: { left: 60, right: 50, top: 30, bottom: 15 },
      xAxis: { type: "category", data: dates, axisLabel: { fontSize: 9, color: textColor } },
      yAxis: [
        { type: "value", axisLabel: { fontSize: 9, color: textColor, formatter: (v: number) => abbreviateNum(v) }, splitLine: { lineStyle: { color: borderColor } } },
        { type: "value", inverse: true, axisLabel: { fontSize: 9, color: textColor, formatter: (v: number) => v + "%" } },
      ],
      series: [
        { type: "line", name: "权益", data: equity, yAxisIndex: 0, smooth: true, lineStyle: { color: "#3b82f6", width: 2 }, areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "#3b82f640" }, { offset: 1, color: "#3b82f605" }] } }, symbol: "none" },
        { type: "line", name: "回撤%", data: dd, yAxisIndex: 1, lineStyle: { color: "#ef4444", width: 1, type: "dashed" }, areaStyle: { color: "#ef444420" }, symbol: "none" },
      ],
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.dispose(); };
  }, [data, dark]);

  return (
    <div>
      <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] text-muted-foreground border-b">
        <span>最终权益: <span className="font-mono font-semibold text-foreground">{abbreviateNum(data.final_equity)}</span></span>
        <span className="text-down">最大回撤: <span className="font-mono font-semibold">{(data.max_drawdown * 100).toFixed(1)}%</span></span>
      </div>
      <div ref={ref} style={{ height: 300, width: "100%" }} />
    </div>
  );
}

// ── Trades ────────────────────────────────────────────────────────────────

function TradePanel({ trades }: { trades?: any[] }) {
  const { t } = useI18n();
  if (!trades || trades.length === 0) {
    return <p className="text-xs text-muted-foreground p-4">{(t as any).ptNoTrades || "No trade records"}</p>;
  }

  return (
    <table className="w-full text-[10px]">
      <thead>
        <tr className="border-b bg-muted/30 text-muted-foreground sticky top-0">
          <th className="px-3 py-1.5 text-left font-medium w-[90px]">{(t as any).ptSymbol || "Code"}</th>
          <th className="px-3 py-1.5 text-left font-medium w-[50px]">{(t as any).ptDirection || "Side"}</th>
          <th className="px-3 py-1.5 text-left font-medium w-[130px]">{(t as any).ptEntryTime || "Time"}</th>
          <th className="px-3 py-1.5 text-left font-medium">{(t as any).ptReason || "Reason"}</th>
        </tr>
      </thead>
      <tbody>
        {trades.map((tr: any, i: number) => (
          <tr key={i} className="border-b border-border/40 hover:bg-muted/30">
            <td className="px-3 py-1 font-mono">{tr.code}</td>
            <td className={`px-3 py-1 font-medium ${tr.side === "BUY" ? "text-down" : "text-green-500"}`}>
              {tr.side === "BUY" ? (t as any).ptLong || "Long" : (t as any).ptShort || "Short"}
            </td>
            <td className="px-3 py-1 text-muted-foreground font-mono">{tr.time}</td>
            <td className="px-3 py-1 text-muted-foreground">{tr.reason || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
