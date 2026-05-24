import { useMemo } from "react";
import type { EquityPoint } from "@/services/paperTrading";

interface Props {
  equity: EquityPoint[];
}

const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

export default function MonthlyReturnHeatmap({ equity }: Props) {
  const grid = useMemo(() => {
    if (equity.length < 2) return { years: [] as number[], months: [] as number[][], values: [] as (number | null)[][] };

    // Calculate monthly returns from equity curve
    const monthlyMap = new Map<string, number>();
    let prevEquity = equity[0].equity;
    let prevMonth = "";

    for (let i = 1; i < equity.length; i++) {
      const d = new Date(equity[i].point_time);
      const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

      if (monthKey !== prevMonth && prevMonth) {
        monthlyMap.set(prevMonth, ((equity[i - 1].equity - prevEquity) / prevEquity) * 100);
        prevEquity = equity[i - 1].equity;
      }
      if (monthKey !== prevMonth) {
        prevEquity = equity[i - 1].equity;
      }
      prevMonth = monthKey;
    }
    // Last month
    if (prevMonth) {
      monthlyMap.set(prevMonth, ((equity[equity.length - 1].equity - prevEquity) / prevEquity) * 100);
    }

    // Build grid
    const yearSet = new Set<number>();
    for (const key of monthlyMap.keys()) {
      yearSet.add(parseInt(key.split("-")[0]));
    }
    const years = [...yearSet].sort();

    const values: (number | null)[][] = years.map((year) =>
      Array.from({ length: 12 }, (_, m) => {
        const key = `${year}-${String(m + 1).padStart(2, "0")}`;
        return monthlyMap.has(key) ? monthlyMap.get(key)! : null;
      })
    );

    return { years, values };
  }, [equity]);

  if (grid.years.length === 0) return <div className="text-xs text-muted-foreground text-center py-4">暂无月度收益数据</div>;

  const maxAbs = Math.max(...grid.values.flat().filter((v): v is number => v != null).map(Math.abs), 1);

  return (
    <div className="space-y-1">
      <div className="flex gap-1 text-[10px] text-muted-foreground mb-1">
        <span className="w-12 shrink-0">年份</span>
        {MONTHS.map((m) => <span key={m} className="flex-1 text-center">{m}</span>)}
      </div>
      {grid.years.map((year, yi) => (
        <div key={year} className="flex gap-1 items-center">
          <span className="w-12 shrink-0 text-[10px] font-mono text-muted-foreground">{year}</span>
          {grid.values[yi].map((v, mi) => (
            <div
              key={mi}
              className="flex-1 aspect-square rounded-sm flex items-center justify-center text-[9px] font-mono"
              style={{
                background: v == null
                  ? "transparent"
                  : v >= 0
                    ? `rgba(239, 68, 68, ${Math.min(v / maxAbs, 1) * 0.7})`
                    : `rgba(34, 197, 94, ${Math.min(Math.abs(v) / maxAbs, 1) * 0.7})`,
              }}
              title={v != null ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}%` : "无数据"}
            >
              {v != null ? `${v >= 0 ? "+" : ""}${v.toFixed(1)}%` : ""}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
