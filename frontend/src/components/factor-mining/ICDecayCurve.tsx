import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";
import { TrendingDown, Clock } from "lucide-react";

interface ICDecayData {
  horizons: number[];
  ic_per_horizon: number[];
  half_life: number | null;
  decay_rate: number;
  interpretation?: string;
}

interface Props {
  data?: ICDecayData;
  className?: string;
}

export function ICDecayCurve({ data, className }: Props) {
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
    if (!chartRef.current || !data || data.horizons.length === 0) return;
    const theme = getChartTheme();

    const halfLifeLine = data.half_life != null ? [
      { xAxis: data.half_life, yAxis: Math.max(...data.ic_per_horizon.map(Math.abs)) },
      { xAxis: data.half_life, yAxis: 0 },
    ] : [];

    chartRef.current.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
        formatter: (params: any) => {
          const d = params[0];
          return `Horizon: ${d.data[0]} days<br/>IC: ${d.data[1].toFixed(6)}`;
        },
      },
      grid: { left: 55, right: 20, top: 10, bottom: 35 },
      xAxis: {
        type: "value",
        name: "Horizon (days)",
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9 },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      yAxis: {
        type: "value",
        name: "|IC|",
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9, formatter: (v: number) => v.toFixed(4) },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      series: [
        {
          type: "line",
          data: data.horizons.map((h, i) => [h, Math.abs(data.ic_per_horizon[i])]),
          smooth: true,
          lineStyle: { color: "#22c55e", width: 2.5 },
          itemStyle: { color: "#22c55e" },
          symbol: "circle",
          symbolSize: 7,
          areaStyle: { color: "rgba(34, 197, 94, 0.1)" },
          markLine: data.half_life != null ? {
            silent: true,
            symbol: "none",
            lineStyle: { color: "#f59e0b", type: "dashed", width: 1.5 },
            label: {
              formatter: `Half-life: ${data.half_life}d`,
              position: "end",
              color: "#f59e0b",
              fontSize: 10,
            },
            data: [{ xAxis: data.half_life }],
          } : undefined,
        },
      ],
    }, true);
  }, [data]);

  if (!data || data.horizons.length === 0) {
    return (
      <div className={cn("border rounded-xl p-4 flex flex-col items-center justify-center text-muted-foreground text-xs gap-1", className)} style={{ height: 280 }}>
        <TrendingDown className="h-4 w-4" />
        IC decay data not available
      </div>
    );
  }

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs flex items-center justify-between">
        <span className="font-medium flex items-center gap-1">
          <TrendingDown className="h-3 w-3" />
          IC Decay Curve
        </span>
        <span className="text-muted-foreground flex items-center gap-2">
          {data.half_life != null && (
            <span className="flex items-center gap-0.5">
              <Clock className="h-2.5 w-2.5" />
              Half-life: {data.half_life}d
            </span>
          )}
          <span>Decay rate: {(data.decay_rate * 100).toFixed(1)}% / step</span>
        </span>
      </div>
      <div ref={containerRef} style={{ height: 280, width: "100%" }} />
      {data.interpretation && (
        <div className="px-3 py-1.5 border-t bg-muted/20 text-[10px] text-muted-foreground">
          {data.interpretation}
        </div>
      )}
    </div>
  );
}
