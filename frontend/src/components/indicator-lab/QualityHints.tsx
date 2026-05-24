import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import type { QualityHint } from "./types";

const SEVERITY_STYLES: Record<string, string> = {
  error: "border-l-danger bg-danger/5 text-danger",
  warn: "border-l-warning bg-warning/5 text-warning",
  info: "border-l-info bg-info/5 text-info",
};

const SEVERITY_LABEL: Record<string, string> = {
  error: "Error",
  warn: "Warn",
  info: "Info",
};

const HINT_MESSAGES: Record<string, string> = {
  EMPTY_CODE: "Code is empty",
  MISSING_INDICATOR_NAME: "Missing my_indicator_name",
  MISSING_INDICATOR_DESCRIPTION: "Missing my_indicator_description",
  MISSING_DF_COPY: "Missing df = df.copy() — work on a copy to avoid side effects",
  MISSING_OUTPUT: "Missing output dict — required for chart rendering",
  MISSING_BUY_SELL_COLUMNS: "No df['buy']/df['sell'] — won't generate trade signals",
  DECLARED_PARAMS_NOT_READ_VIA_PARAMS_GET: "Declared @param not used via params.get()",
  SIGNAL_MARKERS_USE_WHERE_NONE: "Signal markers use .where(None).tolist() pattern",
  NDARRAY_PANDAS_METHOD_MISUSE: "ndarray called like Series — use pd.Series() wrapper",
  HELPER_RETURNS_NDARRAY: "Helper function returns ndarray — may cause pandas method errors",
  FUTURE_DATA_LEAK: "Future data leak detected — look-ahead bias",
  UNKNOWN_STRATEGY_KEY: "Unknown @strategy key",
  NO_STRATEGY_ANNOTATIONS: "No @strategy annotations — risk controls not set",
  NO_STOP_AND_TAKE_PROFIT: "No stop-loss or take-profit configured",
  NO_STOP_LOSS: "No stop-loss configured",
  NO_TAKE_PROFIT: "No take-profit configured",
  ZERO_STOP_AND_TAKE_PROFIT: "Stop-loss and take-profit are both 0",
  ENTRY_PCT_VERY_LOW: "Entry position percentage is very low",
  TRAILING_NO_PCT: "Trailing stop enabled but no trailing stop percentage set",
  EMPTY_PLOTS_AND_SIGNALS: "Empty plots and signals — nothing to display",
};

interface QualityHintsProps {
  hints: QualityHint[];
}

export function QualityHints({ hints }: QualityHintsProps) {
  const { t } = useI18n();
  if (!hints || hints.length === 0) {
    return (
      <div className="text-xs text-muted-foreground p-3 text-center">
        {t.indicatorLabNoIssues}
      </div>
    );
  }

  const errorCount = hints.filter((h) => h.severity === "error").length;
  const warnCount = hints.filter((h) => h.severity === "warn").length;
  const infoCount = hints.filter((h) => h.severity === "info").length;

  return (
    <div className="space-y-1.5">
      {/* Summary */}
      <div className="flex items-center gap-2 px-1 pb-1.5 text-xs text-muted-foreground">
        {errorCount > 0 && <span className="text-danger font-medium">{errorCount} error{errorCount > 1 ? "s" : ""}</span>}
        {warnCount > 0 && <span className="text-warning font-medium">{warnCount} warning{warnCount > 1 ? "s" : ""}</span>}
        {infoCount > 0 && <span className="text-info font-medium">{infoCount} hint{infoCount > 1 ? "s" : ""}</span>}
      </div>

      {/* Hint list */}
      {hints.map((hint, i) => (
        <div
          key={i}
          className={cn(
            "pl-2 pr-1.5 py-1.5 rounded-r text-xs border-l-2",
            SEVERITY_STYLES[hint.severity] || "text-muted-foreground"
          )}
        >
          <div className="flex items-start gap-1.5">
            <span className={cn("font-medium text-[10px] uppercase tracking-wide shrink-0 mt-px")}>
              {SEVERITY_LABEL[hint.severity] || hint.severity}
            </span>
            <span>
              {HINT_MESSAGES[hint.code] || hint.code}
              {hint.params && Object.keys(hint.params).length > 0 && (
                <span className="block mt-0.5 opacity-70">
                  {Object.entries(hint.params)
                    .filter(([, v]) => v !== undefined && v !== "" && v !== null)
                    .map(([k, v]) => {
                      const val = typeof v === "string" ? v : JSON.stringify(v);
                      return `${k}=${val}`;
                    })
                    .join(", ")}
                </span>
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
