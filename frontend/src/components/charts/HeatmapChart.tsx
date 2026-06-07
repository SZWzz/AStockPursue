/**
 * HeatmapChart — renders a 2D parameter heatmap from ExperimentNode output.
 *
 * Data format:
 *   { x_param: string, y_param: string, metric: string,
 *     cells: [{ x: any, y: any, value: number }] }
 */

import { useMemo } from "react";
import { cn } from "@/lib/utils";

export interface HeatmapCell {
  x: string | number;
  y: string | number;
  value: number;
}

export interface HeatmapData {
  xParam: string;
  yParam: string;
  metric: string;
  cells: HeatmapCell[];
}

interface HeatmapChartProps {
  data: HeatmapData;
  className?: string;
  width?: number;
  height?: number;
  colorScale?: "green-red" | "blue-red" | "sequential";
  valueFormat?: (v: number) => string;
}

function defaultFormat(v: number): string {
  return v.toFixed(3);
}

/** Interpolate between two hex colors */
function lerpColor(hexA: string, hexB: string, t: number): string {
  const ah = parseInt(hexA.slice(1), 16);
  const bh = parseInt(hexB.slice(1), 16);
  const ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab = ah & 0xff;
  const br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb = bh & 0xff;
  const rr = Math.round(ar + (br - ar) * t);
  const gg = Math.round(ag + (bg - ag) * t);
  const bl = Math.round(ab + (bb - ab) * t);
  return `#${rr.toString(16).padStart(2, "0")}${gg.toString(16).padStart(2, "0")}${bl.toString(16).padStart(2, "0")}`;
}

const SCALES: Record<string, [string, string, string]> = {
  "green-red": ["#22c55e", "#fef08a", "#ef4444"],
  "blue-red": ["#3b82f6", "#fef08a", "#ef4444"],
  sequential: ["#eff6ff", "#3b82f6", "#1e3a5f"],
};

export function HeatmapChart({
  data,
  className,
  width = 500,
  height = 400,
  colorScale = "blue-red",
  valueFormat = defaultFormat,
}: HeatmapChartProps) {
  const { xVals, yVals, grid } = useMemo(() => {
    const xs = [...new Set(data.cells.map((c) => String(c.x)))].sort();
    const ys = [...new Set(data.cells.map((c) => String(c.y)))].sort();
    const g: Record<string, Record<string, number>> = {};
    for (const c of data.cells) {
      const xk = String(c.x);
      const yk = String(c.y);
      g[xk] ??= {};
      g[xk][yk] = c.value;
    }
    return { xVals: xs, yVals: ys, grid: g };
  }, [data]);

  const [lowC, midC, highC] = SCALES[colorScale] || SCALES["blue-red"];

  const values = data.cells.map((c) => c.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  const margin = { top: 20, right: 20, bottom: 50, left: 60 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const cellW = plotW / xVals.length;
  const cellH = plotH / yVals.length;

  const getColor = (v: number): string => {
    const t = (v - minV) / range; // 0..1
    if (t <= 0.5) return lerpColor(lowC, midC, t * 2);
    return lerpColor(midC, highC, (t - 0.5) * 2);
  };

  const getTextColor = (v: number): string => {
    const t = (v - minV) / range;
    return t > 0.6 ? "white" : "currentColor";
  };

  return (
    <div className={cn("relative", className)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
        {/* Y axis label */}
        <text
          x={12} y={height / 2}
          textAnchor="middle"
          transform={`rotate(-90, 12, ${height / 2})`}
          className="fill-muted-foreground text-[9px]"
        >
          {data.yParam}
        </text>

        {/* Cells */}
        {yVals.map((y, yi) =>
          xVals.map((x, xi) => {
            const v = grid[x]?.[y];
            if (v === undefined) return null;
            return (
              <g key={`${x}-${y}`}>
                <rect
                  x={margin.left + xi * cellW}
                  y={margin.top + yi * cellH}
                  width={cellW - 1}
                  height={cellH - 1}
                  fill={getColor(v)}
                  rx={2}
                />
                <text
                  x={margin.left + xi * cellW + cellW / 2}
                  y={margin.top + yi * cellH + cellH / 2 + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="text-[8px]"
                  fill={getTextColor(v)}
                >
                  {valueFormat(v)}
                </text>
              </g>
            );
          })
        )}

        {/* X axis labels */}
        {xVals.map((x, xi) => (
          <text
            key={`xl-${x}`}
            x={margin.left + xi * cellW + cellW / 2}
            y={height - 8}
            textAnchor="middle"
            className="fill-muted-foreground text-[8px]"
          >
            {x}
          </text>
        ))}

        {/* Y axis labels */}
        {yVals.map((y, yi) => (
          <text
            key={`yl-${y}`}
            x={margin.left - 4}
            y={margin.top + yi * cellH + cellH / 2 + 1}
            textAnchor="end"
            dominantBaseline="middle"
            className="fill-muted-foreground text-[8px]"
          >
            {y}
          </text>
        ))}

        {/* X axis title */}
        <text
          x={margin.left + plotW / 2}
          y={height - 32}
          textAnchor="middle"
          className="fill-muted-foreground text-[9px]"
        >
          {data.xParam}
        </text>

        {/* Legend */}
        <defs>
          <linearGradient id="heatLegend" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={lowC} />
            <stop offset="50%" stopColor={midC} />
            <stop offset="100%" stopColor={highC} />
          </linearGradient>
        </defs>
        <rect x={margin.left} y={height - 22} width={plotW} height={10} fill="url(#heatLegend)" rx={2} />
        <text x={margin.left} y={height - 26} className="fill-muted-foreground text-[7px]">{minV.toFixed(2)}</text>
        <text x={margin.left + plotW} y={height - 26} textAnchor="end" className="fill-muted-foreground text-[7px]">{maxV.toFixed(2)}</text>
      </svg>
    </div>
  );
}
