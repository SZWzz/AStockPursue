import { CheckCircle, XCircle, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QualityHint } from "./types";

interface StrategyVerifyResult {
  success: boolean;
  error: string | null;
  quality_hints: QualityHint[];
  params: { name: string; type: string; default: unknown; description: string }[];
  has_generate_method: boolean;
  has_signal_map_return: boolean;
  symbol_count: number;
}

interface StrategyVerifyPanelProps {
  result: StrategyVerifyResult | null;
}

const SEVERITY_STYLES: Record<string, string> = {
  error: "border-l-danger bg-danger/5 text-danger",
  warn: "border-l-warning bg-warning/5 text-warning",
  info: "border-l-info bg-info/5 text-info",
};

const HINT_MESSAGES: Record<string, string> = {
  EMPTY_CODE: "Code is empty",
  MISSING_CLASS: "Missing SignalEngine class definition",
  MISSING_GENERATE_METHOD: "Missing generate() method on SignalEngine",
  NO_SIGNAL_MAP_RETURN: "generate() does not return signal_map dict",
  MISSING_PANDAS_IMPORT: "Missing pandas/numpy import",
  FUTURE_DATA_LEAK: "Future data leak detected — lookahead bias",
  NO_DATA_VALIDATION: "No data length validation — may crash on short DataFrames",
  SIGNAL_OUT_OF_RANGE: "Signal values outside [-1, 1] range",
};

export function StrategyVerifyPanel({ result }: StrategyVerifyPanelProps) {
  if (!result) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Run verification to check your strategy code.
      </div>
    );
  }

  const hints = result.quality_hints || [];
  const errorCount = hints.filter((h) => h.severity === "error").length;
  const warnCount = hints.filter((h) => h.severity === "warn").length;
  const infoCount = hints.filter((h) => h.severity === "info").length;

  return (
    <div className="space-y-4">
      {/* Overall status */}
      <div
        className={cn(
          "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium",
          result.success
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
        )}
      >
        {result.success ? (
          <CheckCircle className="h-4 w-4 shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 shrink-0" />
        )}
        {result.success ? "Verification passed" : result.error || "Verification failed"}
      </div>

      {/* Contract checks */}
      <div className="space-y-1.5">
        <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider px-1">
          Contract Compliance
        </div>
        <div className="space-y-0.5">
          <ContractCheckItem
            label="SignalEngine class"
            passed={result.has_generate_method}
          />
          <ContractCheckItem
            label="generate() method"
            passed={result.has_generate_method}
          />
          <ContractCheckItem
            label="Returns signal_map"
            passed={result.has_signal_map_return}
          />
          <ContractCheckItem
            label={`Symbols processed: ${result.symbol_count}`}
            passed={result.symbol_count > 0}
          />
        </div>
      </div>

      {/* Params */}
      {result.params && result.params.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider px-1">
            Parameters ({result.params.length})
          </div>
          <div className="space-y-1">
            {result.params.map((p) => (
              <div
                key={p.name}
                className="flex items-center justify-between px-3 py-1.5 rounded-lg text-sm bg-muted/30"
              >
                <span className="font-medium">{p.name}</span>
                <span className="text-muted-foreground font-mono text-xs">
                  {p.type} = {String(p.default)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quality hints */}
      {hints.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 px-1">
            <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
              Quality
            </span>
            <span className="flex items-center gap-1.5 text-xs">
              {errorCount > 0 && (
                <span className="text-danger font-medium">{errorCount} err</span>
              )}
              {warnCount > 0 && (
                <span className="text-warning font-medium">{warnCount} warn</span>
              )}
              {infoCount > 0 && (
                <span className="text-info font-medium">{infoCount} info</span>
              )}
            </span>
          </div>
          <div className="space-y-1">
            {hints.map((hint, i) => (
              <div
                key={i}
                className={cn(
                  "pl-3 pr-2 py-2 rounded-r-lg text-sm border-l-2",
                  SEVERITY_STYLES[hint.severity] || "text-muted-foreground"
                )}
              >
                <div className="flex items-start gap-1.5">
                  {hint.severity === "error" ? (
                    <XCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  ) : hint.severity === "warn" ? (
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  ) : (
                    <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  )}
                  <span className="text-xs leading-snug">
                    {HINT_MESSAGES[hint.code] || hint.code}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ContractCheckItem({ label, passed }: { label: string; passed: boolean }) {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 text-sm">
      {passed ? (
        <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
      ) : (
        <XCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
      )}
      <span className={passed ? "text-foreground" : "text-muted-foreground"}>
        {label}
      </span>
    </div>
  );
}
