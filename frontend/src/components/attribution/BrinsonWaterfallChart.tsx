import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";

interface SectorData {
  sector: string;
  allocation_effect: number;
  selection_effect: number;
  interaction_effect: number;
  total: number;
}

interface Props {
  perSector: SectorData[];
  allocationEffect: number;
  selectionEffect: number;
  interactionEffect: number;
  className?: string;
}

export function BrinsonWaterfallChart({
  perSector,
  allocationEffect,
  selectionEffect,
  interactionEffect,
  className,
}: Props) {
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

    // Build waterfall: allocation, selection, interaction effects per sector
    const sectors = perSector.map((s) => s.sector);
    const allocData = perSector.map((s) => s.allocation_effect);
    const selData = perSector.map((s) => s.selection_effect);
    const interData = perSector.map((s) => s.interaction_effect);

    chartRef.current.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
        formatter: (params: any) => {
          let html = `<div style="font-weight:600;margin-bottom:4px">${params[0]?.axisValue}</div>`;
          params.forEach((p: any) => {
            html += `<div style="display:flex;justify-content:space-between;gap:12px">
              <span>${p.marker} ${p.seriesName}</span>
              <span style="font-family:monospace">${p.value?.toFixed(6)}</span>
            </div>`;
          });
          return html;
        },
      },
      legend: {
        data: ["Allocation", "Selection", "Interaction"],
        bottom: 0,
        textStyle: { color: theme.textColor, fontSize: 11 },
      },
      grid: { left: 60, right: 20, top: 10, bottom: 40 },
      xAxis: {
        type: "category",
        data: sectors,
        axisLabel: { color: theme.axisColor, fontSize: 9, rotate: sectors.length > 8 ? 45 : 0 },
      },
      yAxis: {
        type: "value",
        name: "Effect",
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9, formatter: (v: number) => v.toFixed(4) },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      series: [
        {
          name: "Allocation", type: "bar", stack: "total",
          data: allocData,
          itemStyle: { color: "#3b82f6" },
          emphasis: { focus: "series" },
        },
        {
          name: "Selection", type: "bar", stack: "total",
          data: selData,
          itemStyle: { color: "#22c55e" },
          emphasis: { focus: "series" },
        },
        {
          name: "Interaction", type: "bar", stack: "total",
          data: interData,
          itemStyle: { color: "#a855f7" },
          emphasis: { focus: "series" },
        },
      ],
    }, true);
  }, [perSector]);

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs font-medium">
        Brinson Decomposition by Sector
      </div>
      <div ref={containerRef} style={{ height: 320, width: "100%" }} />
    </div>
  );
}
