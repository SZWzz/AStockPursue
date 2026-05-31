import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";

interface SectorRow {
  sector: string;
  weight: number;
  pnl: number;
  contribution: number;
}

interface Props {
  perSector: SectorRow[];
  concentrationHhi: number;
  className?: string;
}

export function SectorComparisonChart({ perSector, concentrationHhi, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.dispose(); };
  }, []);

  useEffect(() => {
    if (!chartRef.current || perSector.length === 0) return;
    const theme = getChartTheme();

    const sectors = perSector.map((s) => s.sector);
    const weights = perSector.map((s) => s.weight * 100); // to %
    const pnls = perSector.map((s) => s.pnl);
    const contributions = perSector.map((s) => s.contribution);

    chartRef.current.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
      },
      legend: {
        data: ["Weight %", "P&L", "Contribution"],
        bottom: 0,
        textStyle: { color: theme.textColor, fontSize: 11 },
      },
      grid: { left: 70, right: 60, top: 10, bottom: 40 },
      xAxis: {
        type: "category",
        data: sectors,
        axisLabel: { color: theme.axisColor, fontSize: 9, rotate: sectors.length > 8 ? 45 : 0 },
      },
      yAxis: [
        {
          type: "value",
          name: "Weight %",
          nameTextStyle: { color: theme.textColor, fontSize: 10 },
          axisLabel: { color: theme.axisColor, fontSize: 9, formatter: "{value}%" },
          splitLine: { lineStyle: { color: theme.gridColor } },
        },
        {
          type: "value",
          name: "P&L / Contrib",
          nameTextStyle: { color: theme.textColor, fontSize: 10 },
          axisLabel: { color: theme.axisColor, fontSize: 9, formatter: (v: number) => v.toFixed(4) },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "Weight %",
          type: "bar",
          data: weights,
          barWidth: "40%",
          itemStyle: { color: "#3b82f6", borderRadius: [2, 2, 0, 0] },
        },
        {
          name: "P&L",
          type: "line",
          yAxisIndex: 1,
          data: pnls,
          lineStyle: { color: "#f59e0b", width: 2 },
          itemStyle: { color: "#f59e0b" },
          symbol: "circle",
          symbolSize: 5,
        },
        {
          name: "Contribution",
          type: "line",
          yAxisIndex: 1,
          data: contributions,
          lineStyle: { color: "#22c55e", width: 2, type: "dashed" },
          itemStyle: { color: "#22c55e" },
          symbol: "diamond",
          symbolSize: 5,
        },
      ],
    }, true);
  }, [perSector]);

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs font-medium flex items-center justify-between">
        <span>Sector Weight vs P&L</span>
        <span className="text-muted-foreground font-normal">
          HHI: {concentrationHhi.toFixed(4)}
        </span>
      </div>
      <div ref={containerRef} style={{ height: 350, width: "100%" }} />
    </div>
  );
}
