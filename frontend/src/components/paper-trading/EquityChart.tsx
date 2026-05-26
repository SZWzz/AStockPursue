import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import { getChartTheme } from "@/lib/chart-theme";
import { useI18n } from "@/lib/i18n";
import type { EquityPoint } from "@/services/paperTrading";

interface Props {
  data: EquityPoint[];
  minHeight?: number;
}

export default function EquityChart({ data, minHeight = 180 }: Props) {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const [containerHeight, setContainerHeight] = useState(minHeight);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(Math.max(minHeight, entry.contentRect.height));
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [minHeight]);

  useEffect(() => {
    if (!containerRef.current) return;

    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current, getChartTheme());
    }

    const chart = chartRef.current;
    const times = data.map((d) => d.point_time);
    const equity = data.map((d) => d.equity);
    const drawdown = data.map((d) => d.drawdown * 100);

    const gridTop = 8;
    const gridBottom = 30;
    const totalH = containerHeight;
    const mainH = Math.max(40, totalH - gridTop - gridBottom - 50); // 50 for drawdown sub-chart
    const ddTop = gridTop + mainH + 8;
    const ddH = Math.max(20, totalH - ddTop - gridBottom);

    chart.setOption(
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
          { left: 60, right: 20, top: gridTop, height: mainH },
          { left: 60, right: 20, top: ddTop, height: ddH },
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
            markArea: (() => {
              if (data.length < 2) return undefined;
              let peak = Number(data[0].equity), peakIdx = 0, maxDD = 0, ddStart = 0, ddEnd = 0;
              for (let i = 0; i < data.length; i++) {
                const v = Number(data[i].equity);
                if (v > peak) { peak = v; peakIdx = i; }
                const dd = (peak - v) / peak;
                if (dd > maxDD) { maxDD = dd; ddStart = peakIdx; ddEnd = i; }
              }
              if (maxDD < 0.01) return undefined;
              return {
                silent: true,
                data: [[{ xAxis: data[ddStart].point_time }, { xAxis: data[ddEnd].point_time }]],
                label: { show: true, position: "insideTop", formatter: `最大回撤 ${(maxDD * 100).toFixed(1)}%`, fontSize: 10 },
                itemStyle: { color: "rgba(239, 68, 68, 0.08)" },
              };
            })(),
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

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, [data, t, containerHeight]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight }} />;
}
