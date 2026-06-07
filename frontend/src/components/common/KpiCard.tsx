import { type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";

interface KpiCardProps {
  label: string;
  value?: number;
  formattedValue?: string;
  change?: number;
  changeLabel?: string;
  sparkline?: ReactNode;
  className?: string;
  /** Use count-up animation for value */
  animate?: boolean;
  /** Number of decimal places for animated value */
  decimals?: number;
}

export function KpiCard({
  label,
  value,
  formattedValue,
  change,
  changeLabel,
  sparkline,
  className,
  animate = false,
  decimals = 0,
}: KpiCardProps) {
  const animated = useCountUp({
    to: value ?? 0,
    duration: 200,
    decimals,
    enabled: animate && value !== undefined,
  });

  const displayValue =
    animate && value !== undefined
      ? animated.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      : formattedValue ?? (value !== undefined ? value.toLocaleString() : "—");

  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;

  return (
    <div
      className={cn(
        "card-metric bg-card border border-border-subtle rounded-lg p-3 flex flex-col gap-1 min-w-0",
        className,
      )}
    >
      {/* Label */}
      <span className="overline text-[10px] font-semibold uppercase tracking-[0.05em] text-muted-foreground">
        {label}
      </span>

      {/* Value */}
      <span className="font-mono text-lg font-bold text-foreground tabular-nums tracking-tight">
        {displayValue}
      </span>

      {/* Change indicator */}
      {(change !== undefined || changeLabel) && (
        <div className="flex items-center gap-1.5">
          {change !== undefined && (
            <span
              className={cn(
                "font-mono text-[11px] tabular-nums font-medium",
                isPositive ? "text-up" : isNegative ? "text-down" : "text-muted-foreground",
              )}
            >
              {isPositive ? "↑" : isNegative ? "↓" : ""}
              {change > 0 ? "+" : ""}
              {change.toFixed(2)}%
            </span>
          )}
          {changeLabel && (
            <span className="text-[10px] text-muted-foreground">{changeLabel}</span>
          )}
        </div>
      )}

      {/* Optional sparkline */}
      {sparkline && <div className="mt-1 -mx-1">{sparkline}</div>}
    </div>
  );
}

/** Grid container for KPI cards — 4 columns on desktop, 2 on mobile */
export function KpiGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid grid-cols-2 lg:grid-cols-4 gap-2", className)}>
      {children}
    </div>
  );
}
