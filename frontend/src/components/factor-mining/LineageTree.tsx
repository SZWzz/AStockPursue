import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";
import type { EliteEntry } from "@/types/api";
import { GitBranch, Clock, TrendingUp } from "lucide-react";

interface Props {
  elites: EliteEntry[];
  className?: string;
}

export function LineageTree({ elites, className }: Props) {
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
    if (!chartRef.current || elites.length === 0) return;
    const theme = getChartTheme();

    // Build a Gantt-style chart showing each elite's lifespan across generations
    const categories = elites.map((e) => {
      const formula = e.formula.length > 40 ? e.formula.slice(0, 40) + "..." : e.formula;
      return formula;
    });

    const data = elites.map((e, i) => ({
      name: `Elite ${i + 1}`,
      value: [i, e.first_seen_gen, e.last_seen_gen, e.best_ic, e.survival_gens],
      itemStyle: {
        color: e.survival_gens >= 8 ? "#f59e0b"
          : e.survival_gens >= 5 ? "#a855f7"
            : "#3b82f6",
        borderRadius: 4,
      },
    }));

    const maxGen = Math.max(...elites.map((e) => e.last_seen_gen), 10);

    chartRef.current.setOption({
      tooltip: {
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
        formatter: (params: any) => {
          const d = params.data?.value;
          if (!d) return "";
          return `<div style="font-weight:600;margin-bottom:4px">${params.name}</div>
            <div>Generations: G${d[1]} → G${d[2]}</div>
            <div>Survival: ${d[4]} gens</div>
            <div>Best IC: ${d[3].toFixed(4)}</div>`;
        },
      },
      grid: { left: 180, right: 30, top: 10, bottom: 30 },
      xAxis: {
        type: "value",
        name: "Generation",
        min: 0,
        max: maxGen,
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9 },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLabel: {
          color: theme.axisColor,
          fontSize: 9,
          width: 160,
          overflow: "truncate",
        },
      },
      series: [{
        type: "custom",
        renderItem: (_params: any, api: any) => {
          const catIdx = api.value(0);
          const start = api.coord([api.value(1), catIdx]);
          const end = api.coord([api.value(2), catIdx]);
          const height = api.size([0, 1])[1] * 0.6;

          return {
            type: "rect",
            shape: {
              x: start[0],
              y: start[1] - height / 2,
              width: Math.max(end[0] - start[0], 4),
              height: height,
            },
            style: {
              fill: api.visual("color"),
            },
          };
        },
        data: data,
        encode: { x: [1, 2], y: [0] },
      }],
    }, true);
  }, [elites]);

  if (elites.length === 0) {
    return (
      <div className={cn("border rounded-xl p-4 flex flex-col items-center justify-center text-muted-foreground text-xs gap-1", className)} style={{ height: 300 }}>
        <GitBranch className="h-4 w-4" />
        Elite lineage will appear after 3+ generations of evolution
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs font-medium flex items-center justify-between">
        <span className="flex items-center gap-1">
          <GitBranch className="h-3 w-3" />
          Factor Lineage (Gantt view)
        </span>
        <span className="text-muted-foreground font-normal flex items-center gap-2">
          <span className="flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" />
            Legend:
          </span>
          <span className="text-amber-500">8+ gens</span>
          <span className="text-purple-500">5-7 gens</span>
          <span className="text-blue-500">3-4 gens</span>
        </span>
      </div>
      <div ref={containerRef} style={{ height: Math.max(200, elites.length * 40 + 60), width: "100%" }} />
    </div>
  );
}
