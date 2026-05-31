import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";
import { TrendingUp, CheckSquare, Square } from "lucide-react";

interface RunSnapshot {
  id: string;
  type: string;
  status: string;
  candidates_count?: number;
  created_at?: string;
  config?: Record<string, unknown>;
  generations?: {
    generation: number;
    best_ic: number;
    best_fitness: number;
    diversity: number;
  }[];
}

interface Props {
  runs: RunSnapshot[];
  className?: string;
}

const COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

export function RunComparisonView({ runs, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.dispose(); };
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    const theme = getChartTheme();

    const activeRuns = runs.filter((r) => selectedRuns.size === 0 || selectedRuns.has(r.id));

    const series = activeRuns.map((run, i) => {
      const gens = run.generations || [];
      const color = COLORS[i % COLORS.length];
      return {
        name: `${run.type?.toUpperCase() || "GP"} ${run.id?.slice(0, 6)}`,
        type: "line" as const,
        data: gens.map((g) => [g.generation, g.best_ic]),
        smooth: true,
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        symbol: "circle",
        symbolSize: 3,
      };
    });

    chartRef.current.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
      },
      legend: {
        type: "scroll",
        bottom: 0,
        textStyle: { color: theme.textColor, fontSize: 10 },
      },
      grid: { left: 55, right: 20, top: 10, bottom: 50 },
      xAxis: {
        type: "value",
        name: "Generation",
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9 },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      yAxis: {
        type: "value",
        name: "Best IC",
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9, formatter: (v: number) => v.toFixed(4) },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      series,
    }, true);
  }, [runs, selectedRuns]);

  const toggleRun = (id: string) => {
    setSelectedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const completedRuns = runs.filter((r) => r.status === "completed" && r.generations?.length);

  if (completedRuns.length === 0) {
    return (
      <div className={cn("border rounded-xl p-4 flex items-center justify-center text-muted-foreground text-xs", className)} style={{ height: 300 }}>
        <TrendingUp className="h-4 w-4 mr-2" />
        Complete multiple GP runs to compare evolution curves
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl flex flex-col", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs font-medium flex items-center justify-between">
        <span className="flex items-center gap-1">
          <TrendingUp className="h-3 w-3" />
          Run Comparison ({completedRuns.length} runs)
        </span>
        <span className="text-muted-foreground font-normal">
          {selectedRuns.size > 0 ? `${selectedRuns.size} selected` : "All shown"}
        </span>
      </div>
      {/* Run selector */}
      <div className="px-3 py-2 flex flex-wrap gap-2 text-[10px] border-b bg-muted/10">
        {completedRuns.map((run) => (
          <button
            key={run.id}
            onClick={() => toggleRun(run.id)}
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 rounded border transition",
              selectedRuns.has(run.id) || selectedRuns.size === 0
                ? "bg-primary/10 border-primary/30 text-primary"
                : "border-border text-muted-foreground hover:bg-muted"
            )}
          >
            {selectedRuns.has(run.id) || selectedRuns.size === 0 ? (
              <CheckSquare className="h-3 w-3" />
            ) : (
              <Square className="h-3 w-3" />
            )}
            <span className="font-mono">{run.id?.slice(0, 8)}</span>
            <span className="opacity-60">{run.type}</span>
          </button>
        ))}
      </div>
      <div ref={containerRef} style={{ height: 320, width: "100%" }} />
    </div>
  );
}
