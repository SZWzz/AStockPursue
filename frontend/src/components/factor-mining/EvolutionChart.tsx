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
