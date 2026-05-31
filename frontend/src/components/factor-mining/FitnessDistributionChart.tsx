import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";
import type { FitnessDistribution } from "@/types/api";
import { Activity } from "lucide-react";

interface Props {
  distribution?: FitnessDistribution;
  className?: string;
}

export function FitnessDistributionChart({ distribution, className }: Props) {
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
    if (!chartRef.current || !distribution || distribution.bins.length < 2) return;

    const theme = getChartTheme();
    const binCenters = distribution.bins.slice(0, -1).map(
      (b, i) => (b + distribution.bins[i + 1]) / 2
    );

    chartRef.current.setOption(
      {
        tooltip: {
          trigger: "axis",
          backgroundColor: theme.tooltipBg,
          borderColor: theme.tooltipBorder,
          textStyle: { color: theme.tooltipText, fontSize: 12 },
          formatter: (params: any) => {
            const d = params[0];
            return `Fitness ~${d.data[0].toFixed(4)}<br/>Count: ${d.data[1]}`;
          },
        },
        grid: { left: 45, right: 15, top: 10, bottom: 30 },
        xAxis: {
          type: "value",
          name: "Fitness",
          nameTextStyle: { color: theme.textColor, fontSize: 10 },
          axisLabel: { color: theme.axisColor, fontSize: 9, formatter: (v: number) => v.toFixed(3) },
          splitLine: { lineStyle: { color: theme.gridColor } },
        },
        yAxis: {
          type: "value",
          name: "Count",
          nameTextStyle: { color: theme.textColor, fontSize: 10 },
          axisLabel: { color: theme.axisColor, fontSize: 9 },
          splitLine: { lineStyle: { color: theme.gridColor } },
        },
        series: [
          {
            type: "bar",
            data: distribution.counts.map((c, i) => [binCenters[i], c]),
            barWidth: "90%",
            itemStyle: {
              color: {
                type: "linear",
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: "#22c55e" },
                  { offset: 1, color: "#166534" },
                ],
              },
              borderRadius: [2, 2, 0, 0],
            },
          },
          {
            type: "line",
            name: "Median",
            data: [
              [distribution.median, 0],
              [distribution.median, Math.max(...distribution.counts)],
            ],
            lineStyle: { color: "#f59e0b", width: 1.5, type: "dashed" },
            symbol: "none",
            silent: true,
          },
        ],
      },
      true
    );
  }, [distribution]);

  if (!distribution || distribution.bins.length < 2) {
    return (
      <div className={cn("border rounded-xl p-3 flex flex-col items-center justify-center text-muted-foreground text-xs gap-1", className)} style={{ height: 200 }}>
        <Activity className="h-4 w-4" />
        Waiting for fitness data...
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 flex items-center justify-between text-xs">
        <span className="font-medium flex items-center gap-1">
          <Activity className="h-3 w-3" />
          Population Fitness Distribution
        </span>
        <span className="text-muted-foreground">
          Q25: {distribution.q25.toFixed(4)} | Median: {distribution.median.toFixed(4)} | Q75: {distribution.q75.toFixed(4)}
        </span>
      </div>
      <div ref={containerRef} style={{ height: 200, width: "100%" }} />
    </div>
  );
}
