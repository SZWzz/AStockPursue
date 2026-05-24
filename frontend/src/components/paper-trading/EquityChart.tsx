import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { getChartTheme } from "@/lib/chart-theme";
import { useI18n } from "@/lib/i18n";
import type { EquityPoint } from "@/services/paperTrading";

interface Props {
  data: EquityPoint[];
  height?: number;
}

export default function EquityChart({ data, height = 300 }: Props) {
  const { t } = useI18n();
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current, getChartTheme());
    }

    const times = data.map((d) => d.point_time);
    const equity = data.map((d) => d.equity);
    const drawdown = data.map((d) => d.drawdown * 100);

    instanceRef.current.setOption(
      {
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
        },
        legend: {
          data: [t.ptEquityLegend, t.ptDrawdownLegend],
          bottom: 0,
        },
        grid: [
          { left: 60, right: 20, top: 20, height: "70%" },
          { left: 60, right: 20, top: "78%", height: "18%" },
        ],
        xAxis: [
          {
            type: "category",
            data: times,
            gridIndex: 0,
            axisLabel: { show: false },
          },
          {
            type: "category",
            data: times,
            gridIndex: 1,
            axisLabel: {
              formatter: (value: string) => {
                const d = new Date(value);
                return `${d.getMonth() + 1}/${d.getDate()}`;
              },
            },
          },
        ],
        yAxis: [
          {
            type: "value",
            gridIndex: 0,
            axisLabel: { formatter: (v: number) => (v / 10000).toFixed(0) + t.ptWan },
          },
          {
            type: "value",
            gridIndex: 1,
            axisLabel: { formatter: "{value}%" },
            inverse: true,
          },
        ],
        series: [
          {
            name: t.ptEquityLegend,
            type: "line",
            data: equity,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 2 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.02)" },
              ]),
            },
          },
          {
            name: t.ptDrawdownLegend,
            type: "line",
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: drawdown,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 1, color: "#ef4444" },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "rgba(239, 68, 68, 0.3)" },
                { offset: 1, color: "rgba(239, 68, 68, 0.02)" },
              ]),
            },
          },
        ],
      },
      true
    );

    return () => {
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, [data, t]);

  return <div ref={chartRef} style={{ width: "100%", height }} />;
}
