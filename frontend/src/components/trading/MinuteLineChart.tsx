import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { getChartTheme } from "@/lib/chart-theme";
import { abbreviateNum } from "@/lib/formatters";
import { echarts } from "@/lib/echarts";
import { useDarkMode } from "@/hooks/useDarkMode";
import type { MinuteBar } from "@/types/api";

interface Props {
  data: MinuteBar[];
  preClose?: number | null;
  symbol?: string;
  height?: number;
}

/** Per-minute price/volume trace (分时图) using ECharts. */
export function MinuteLineChart({ data, preClose, symbol, height = 500 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const { dark } = useDarkMode();

  useEffect(() => {
    if (!containerRef.current) return;

    const theme = getChartTheme();
    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current);
    }
    const chart = chartRef.current;

    if (!data || data.length === 0) {
      chart.clear();
      return;
    }

    const times = data.map((d) => d.time);
    const prices = data.map((d) => d.price);
    const volumes = data.map((d) => d.volume);
    const amounts = data.map((d) => d.amount ?? 0);

    const priceMin = Math.min(...prices) * 0.998;
    const priceMax = Math.max(...prices) * 1.002;
    const pc = preClose ?? prices[0];
    const isUp = prices.length > 0 && prices[prices.length - 1] >= pc;

    // Shade the lunch break period (11:30–13:00) for A-shares
    const lunchMark: { xAxis: string }[] = [];
    const hasLunch = times.some((t) => t >= "11:30") && times.some((t) => t >= "13:00");
    if (hasLunch) {
      lunchMark.push({ xAxis: "11:30" }, { xAxis: "13:00" });
    }

    chart.setOption(
      {
        backgroundColor: "transparent",
        animation: false,
        tooltip: {
          trigger: "axis",
          backgroundColor: theme.tooltipBg,
          borderColor: theme.tooltipBorder,
          textStyle: { color: theme.tooltipText, fontSize: 11 },
          formatter: (params: { data?: number; axisValue?: string; seriesName?: string }[]) => {
            if (!params || params.length === 0) return "";
            const t = params[0]?.axisValue ?? "";
            const hoveredPrice = params[0]?.data;  // price at the hovered minute
            let html = `<div style="font-weight:600;margin-bottom:4px">${symbol ? symbol + " " : ""}${t}</div>`;
            for (const p of params) {
              if (!p || p.data == null) continue;
              const val = p.seriesName === "成交量" ? abbreviateNum(p.data) : p.data.toFixed(2);
              html += `<div style="display:flex;justify-content:space-between;gap:24px"><span>${p.seriesName}</span><span style="font-weight:500">${val}</span></div>`;
            }
            if (pc && hoveredPrice != null) {
              const chg = ((hoveredPrice - pc) / pc * 100).toFixed(2);
              const pointUp = hoveredPrice >= pc;
              html += `<div style="display:flex;justify-content:space-between;gap:24px;margin-top:4px;color:${pointUp ? theme.upColor : theme.downColor}"><span>涨跌幅</span><span style="font-weight:500">${Number(chg) >= 0 ? '+' : ''}${chg}%</span></div>`;
            }
            return html;
          },
        },
        axisPointer: { link: [{ xAxisIndex: "all" }] },
        grid: [
          { left: 8, right: 8, top: 16, height: "62%", containLabel: false },
          { left: 8, right: 8, top: "78%", height: "16%", containLabel: false },
        ],
        xAxis: [
          {
            type: "category", data: times, gridIndex: 0,
            axisLine: { lineStyle: { color: theme.axisColor } },
            axisTick: { show: false },
            axisLabel: {
              color: theme.textColor, fontSize: 10,
              interval: Math.max(1, Math.floor(times.length / 8) - 1),
            },
            splitLine: { show: false },
          },
          {
            type: "category", data: times, gridIndex: 1,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { show: false },
            splitLine: { show: false },
          },
        ],
        yAxis: [
          {
            type: "value", gridIndex: 0, min: priceMin, max: priceMax,
            axisLabel: { color: theme.textColor, fontSize: 10, formatter: (v: number) => v.toFixed(2) },
            splitLine: { lineStyle: { color: theme.gridColor, type: "dashed" } },
            scale: true,
          },
          {
            type: "value", gridIndex: 1,
            axisLabel: { show: false },
            splitLine: { show: false },
          },
        ],
        visualMap: {
          show: false,
          seriesIndex: 2,
          pieces: hasLunch ? [
            { lt: times.indexOf("11:30"), color: "rgba(128,128,128,0.05)" },
            { gte: times.indexOf("13:00"), color: "rgba(128,128,128,0.05)" },
          ] : [],
        },
        series: [
          {
            name: "价格", type: "line", data: prices, xAxisIndex: 0, yAxisIndex: 0,
            symbol: "none", smooth: true,
            lineStyle: { color: isUp ? theme.upColor : theme.downColor, width: 1.5 },
            areaStyle: {
              color: new (echarts as unknown as { graphic: { LinearGradient: new (arg0: number, arg1: number, arg2: number, arg3: number, arg4: { offset: number; color: string }[]) => unknown } }).graphic.LinearGradient(
                0, 0, 0, 1,
                [
                  { offset: 0, color: (isUp ? theme.upColor : theme.downColor) + "33" },
                  { offset: 1, color: "rgba(0,0,0,0)" },
                ]
              ),
            },
            markLine: pc ? {
              silent: true, symbol: "none",
              lineStyle: { color: theme.textColor, type: "dashed", width: 1, opacity: 0.5 },
              data: [{ yAxis: pc, label: { formatter: `昨收 ${pc}`, fontSize: 10, color: theme.textColor } }],
            } : undefined,
          },
          {
            name: "均价", type: "line", data: (() => {
              let cum = 0, cumAmt = 0;
              return prices.map((p, i) => {
                const amt = amounts[i] ?? p * (volumes[i] ?? 0);
                cum += amt;
                cumAmt += (volumes[i] ?? 0);
                return cumAmt > 0 ? cum / cumAmt : p;
              });
            })(), xAxisIndex: 0, yAxisIndex: 0,
            symbol: "none", smooth: true,
            lineStyle: { color: theme.warningColor, width: 1, type: "dotted" },
          },
          {
            name: "成交量", type: "bar", data: volumes, xAxisIndex: 1, yAxisIndex: 1,
            itemStyle: {
              color: (params: { dataIndex: number }) => {
                const p = prices[params.dataIndex];
                const prev = params.dataIndex > 0 ? prices[params.dataIndex - 1] : pc;
                return p >= (prev ?? p) ? theme.upColor + "66" : theme.downColor + "66";
              },
              borderRadius: [1, 1, 0, 0],
            },
          },
        ],
      },
      { notMerge: true }
    );

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(containerRef.current);
    return () => {
      ro.disconnect();
    };
  }, [data, preClose, symbol, dark]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  if (!data || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center border rounded-xl bg-muted/10 text-muted-foreground text-sm"
        style={{ height }}
      >
        暂无分时数据
      </div>
    );
  }

  return (
    <div className="border rounded-xl bg-card overflow-hidden">
      {/* Header */}
      {preClose && data.length > 0 && (() => {
        const last = data[data.length - 1].price;
        const chg = ((last - preClose) / preClose * 100);
        const isUp = chg >= 0;
        return (
          <div className="flex items-center gap-3 px-3 py-2 border-b text-xs">
            {symbol && <span className="font-mono font-medium">{symbol}</span>}
            <span className={cn("font-mono text-sm font-bold", isUp ? "text-up" : "text-down")}>
              {last.toFixed(2)}
            </span>
            <span className={cn("font-mono", isUp ? "text-up" : "text-down")}>
              {isUp ? "+" : ""}{chg.toFixed(2)}%
            </span>
            <span className="text-muted-foreground ml-auto">昨收 {preClose}</span>
          </div>
        );
      })()}
      <div ref={containerRef} style={{ height: height - (preClose ? 36 : 0) }} />
    </div>
  );
}
