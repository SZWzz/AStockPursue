import { useI18n } from "@/lib/i18n";
import type { RunSummary } from "@/services/paperTrading";

interface Props {
  run: RunSummary;
  isActive: boolean;
  onSelect: (id: string) => void;
  onStart: (id: string) => void;
  onStop: (id: string) => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
}

const statusColors: Record<string, string> = {
  running: "bg-green-500",
  paused: "bg-yellow-500",
  stopped: "bg-gray-400",
  error: "bg-red-500",
};

export default function PaperTradingCard({
  run, isActive, onSelect, onStart, onStop, onPause, onResume, onDelete,
}: Props) {
  const { t } = useI18n();

  const stateKey = run.state === "flat" ? "ptStateFlat" : run.state === "long" ? "ptStateLong" : "ptStateShort";

  return (
    <div
      className={`border rounded-lg p-4 cursor-pointer transition-shadow hover:shadow-md ${
        isActive ? "border-blue-500 ring-1 ring-blue-300" : "border-gray-200"
      }`}
      onClick={() => onSelect(run.id)}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${statusColors[run.status] || "bg-gray-400"}`}
            title={run.status}
          />
          <h3 className="font-semibold text-sm truncate max-w-[180px]">{run.run_name}</h3>
        </div>
        <span className="text-xs text-gray-500">{run.market}</span>
      </div>

      <div className="grid grid-cols-2 gap-1 mb-3 text-sm">
        <div>
          <span className="text-gray-500">{t.ptEquity}</span>
          <p className="font-mono font-medium">
            {run.current_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div>
          <span className="text-gray-500">{t.ptReturn}</span>
          <p className={`font-mono font-medium ${run.total_return_pct >= 0 ? "text-up" : "text-down"}`}>
            {run.total_return_pct >= 0 ? "+" : ""}{run.total_return_pct.toFixed(2)}%
          </p>
        </div>
        <div>
          <span className="text-gray-500">{t.ptPositions}</span>
          <p className="font-mono">
            {run.open_positions}
            {run.state !== "flat" && (
              <span className="text-xs text-gray-400 ml-1">({t[stateKey as keyof typeof t]})</span>
            )}
          </p>
        </div>
        <div>
          <span className="text-gray-500">{t.ptTrades}</span>
          <p className="font-mono">{run.trade_count}</p>
        </div>
      </div>

      <div className="h-10 bg-gray-50 rounded mb-3 flex items-center justify-center text-xs text-gray-400">
        {run.last_bar_time
          ? `${t.ptLastBar}: ${new Date(run.last_bar_time).toLocaleDateString()}`
          : t.ptNoData}
      </div>

      <div className="flex gap-1 flex-wrap" onClick={(e) => e.stopPropagation()}>
        {run.status === "stopped" || run.status === "error" ? (
          <button
            className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
            onClick={() => onStart(run.id)}
          >
            {t.ptStart}
          </button>
        ) : run.status === "running" ? (
          <>
            <button
              className="px-3 py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600"
              onClick={() => onPause(run.id)}
            >
              {t.ptPause}
            </button>
            <button
              className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
              onClick={() => onStop(run.id)}
            >
              {t.ptStop}
            </button>
          </>
        ) : run.status === "paused" ? (
          <>
            <button
              className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
              onClick={() => onResume(run.id)}
            >
              {t.ptResume}
            </button>
            <button
              className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
              onClick={() => onStop(run.id)}
            >
              {t.ptStop}
            </button>
          </>
        ) : null}
        {run.status !== "running" && (
          <button
            className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            onClick={() => onDelete(run.id)}
          >
            {t.ptDelete}
          </button>
        )}
      </div>
    </div>
  );
}
