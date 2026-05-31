import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";

interface Props {
  betas: Record<string, number>;
  contributions: Record<string, number>;
  rSquared: number;
  residualReturn: number;
  className?: string;
}

export function FactorExposureChart({
  betas,
  contributions,
  rSquared,
  residualReturn,
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
    if (!chartRef.current || Object.keys(betas).length === 0) return;
    const theme = getChartTheme();

    const factors = Object.keys(betas);
    const betaVals = factors.map((k) => betas[k]);

    chartRef.current.setOption({
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText, fontSize: 12 },
      },
      legend: {
        data: ["Beta", "Contribution"],
        bottom: 0,
        textStyle: { color: theme.textColor, fontSize: 11 },
      },
      grid: { left: 80, right: 20, top: 10, bottom: 40 },
      xAxis: {
        type: "value",
        name: "Beta",
        nameTextStyle: { color: theme.textColor, fontSize: 10 },
        axisLabel: { color: theme.axisColor, fontSize: 9 },
        splitLine: { lineStyle: { color: theme.gridColor } },
      },
      yAxis: {
        type: "category",
        data: factors.map((f) => f.length > 25 ? f.slice(0, 25) + "..." : f),
        axisLabel: { color: theme.axisColor, fontSize: 9 },
      },
      series: [
        {
          name: "Beta",
          type: "bar",
          data: betaVals.map((v) => ({
            value: v,
            itemStyle: {
              color: v >= 0 ? "#22c55e" : "#ef4444",
              borderRadius: v >= 0 ? [0, 2, 2, 0] : [2, 0, 0, 2],
            },
          })),
          barWidth: "60%",
        },
      ],
    }, true);
  }, [betas, contributions]);

  return (
    <div className={cn("border rounded-xl overflow-hidden", className)}>
      <div className="px-3 py-1.5 border-b bg-muted/30 text-xs font-medium flex items-center justify-between">
        <span>Factor Exposure (R² = {rSquared.toFixed(4)})</span>
        <span className="text-muted-foreground font-normal">
          Residual: {residualReturn.toFixed(6)}
        </span>
      </div>
      <div ref={containerRef} style={{ height: 350, width: "100%" }} />
    </div>
  );
}
