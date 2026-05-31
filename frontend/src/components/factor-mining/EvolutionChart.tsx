import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";

interface GenerationSnapshot {
  generation: number;
  best_fitness: number;
  mean_fitness: number;
  std_fitness: number;
  best_ic: number;
  diversity: number;
  best_formula?: string;
}

interface Props {
  generations: GenerationSnapshot[];
  className?: string;
}

export function EvolutionChart({ generations, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current || generations.length === 0) return;

    const gens = generations.map((g) => g.generation);
    const theme = getChartTheme();

    chartRef.current.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
        formatter: (params: any) => {
          const genIdx = params[0]?.dataIndex;
          const gen = generations[genIdx];
          let html = `<div style="font-weight:600;margin-bottom:4px">Generation ${gen?.generation || genIdx + 1}</div>`;
          params.forEach((p: any) => {
            html += `<div style="display:flex;justify-content:space-between;gap:12px"><span>${p.marker} ${p.seriesName}</span><span style="font-family:monospace">${typeof p.value === 'number' ? p.value.toFixed(4) : p.value}</span></div>`;
          });
          if (gen?.best_formula) {
            html += `<div style="margin-top:6px;padding-top:4px;border-top:1px solid ${theme.tooltipBorder};font-size:10px;color:#a0a0a0;max-width:280px;word-break:break-all"><code>${gen.best_formula}</code></div>`;
          }
          return html;
        },
      },
      legend: {
        data: ["Best IC", "Mean Fitness", "Diversity"],
        bottom: 0,
        textStyle: { color: theme.textColor, fontSize: 11 },
      },
      grid: { left: 50, right: 20, top: 10, bottom: 40 },
      xAxis: {
        type: "category" as const,
        data: gens,
        name: "Generation",
        nameTextStyle: { color: theme.textColor, fontSize: 11 },
        axisLabel: { color: theme.axisColor, fontSize: 10 },
      },
      yAxis: {
        type: "value" as const,
        name: "IC / Fitness",
        nameTextStyle: { color: theme.textColor, fontSize: 11 },
        axisLabel: { color: theme.axisColor, fontSize: 10 },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      series: [
        {
          name: "Best IC",
          type: "line",
          data: generations.map((g) => g.best_ic),
          smooth: true,
          lineStyle: { color: theme.upColor, width: 2 },
          itemStyle: { color: theme.upColor },
          symbol: "circle",
          symbolSize: 4,
        },
        {
          name: "Mean Fitness",
          type: "line",
          data: generations.map((g) => g.mean_fitness),
          smooth: true,
          lineStyle: { color: "#3b82f6", width: 1.5, type: "dashed" },
          itemStyle: { color: "#3b82f6" },
          symbol: "none",
        },
        {
          name: "Diversity",
          type: "line",
          data: generations.map((g) => g.diversity),
          smooth: true,
          lineStyle: { color: "#a855f7", width: 1, type: "dotted" },
          itemStyle: { color: "#a855f7" },
          symbol: "none",
        },
      ],
    }, true);
  }, [generations]);

  if (generations.length === 0) {
    return (
      <div className={cn("border rounded-xl p-4 flex items-center justify-center text-muted-foreground text-sm", className)} style={{ height: 300 }}>
        Start an evolution run to see the IC curve
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div ref={containerRef} style={{ height: 300, width: "100%" }} />
    </div>
  );
}
