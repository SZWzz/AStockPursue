import { useI18n } from "@/lib/i18n";
import type { Trade } from "@/services/paperTrading";

interface Props {
  trades: Trade[];
}

export default function TradeHistoryTable({ trades }: Props) {
  const { t } = useI18n();

  if (trades.length === 0) {
    return <div className="text-center text-muted-foreground py-8 text-sm">{t.ptNoTrades}</div>;
  }

  const reasonKeyMap: Record<string, string> = {
    signal: "ptReasonSignal",
    stop_loss: "ptReasonStopLoss",
    take_profit: "ptReasonTakeProfit",
    trailing_stop: "ptReasonTrailingStop",
    daily_loss: "ptReasonDailyLoss",
    end_of_run: "ptReasonEndOfRun",
    manual: "ptReasonManual",
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-3">{t.ptSymbol}</th>
            <th className="py-2 pr-3">{t.ptDirection}</th>
            <th className="py-2 pr-3 text-right">{t.ptEntryPrice}</th>
            <th className="py-2 pr-3 text-right">{t.ptExitPrice}</th>
            <th className="py-2 pr-3 text-right">{t.ptSize}</th>
            <th className="py-2 pr-3 text-right">{t.ptUnrealizedPnl}</th>
            <th className="py-2 pr-3 text-right">{t.ptPnlPct}</th>
            <th className="py-2 pr-3">{t.ptReason}</th>
            <th className="py-2 pr-3">{t.ptEntryTime}</th>
            <th className="py-2 pr-3">{t.ptExitTime}</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((tr) => {
            const reasonKey = reasonKeyMap[tr.exit_reason] || tr.exit_reason;
            return (
              <tr key={tr.id} className="border-b last:border-0 hover:bg-muted/20">
                <td className="py-2 pr-3 font-mono font-medium">{tr.symbol}</td>
                <td className="py-2 pr-3">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                      tr.direction === 1 ? "bg-up/10 text-up" : "bg-down/10 text-down"
                    }`}
                  >
                    {tr.direction === 1 ? t.ptLong : t.ptShort}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right font-mono">{tr.entry_price.toFixed(3)}</td>
                <td className="py-2 pr-3 text-right font-mono">{tr.exit_price.toFixed(3)}</td>
                <td className="py-2 pr-3 text-right font-mono">{tr.size.toFixed(0)}</td>
                <td className={`py-2 pr-3 text-right font-mono ${tr.pnl >= 0 ? "text-up" : "text-down"}`}>
                  {tr.pnl >= 0 ? "+" : ""}{tr.pnl.toFixed(2)}
                </td>
                <td className={`py-2 pr-3 text-right font-mono ${tr.pnl_pct >= 0 ? "text-up" : "text-down"}`}>
                  {tr.pnl_pct >= 0 ? "+" : ""}{tr.pnl_pct.toFixed(2)}%
                </td>
                <td className="py-2 pr-3">
                  <span className="text-xs bg-muted/30 px-1.5 py-0.5 rounded">
                    {t[reasonKey as keyof typeof t] || tr.exit_reason}
                  </span>
                </td>
                <td className="py-2 pr-3 text-xs text-muted-foreground">
                  {new Date(tr.entry_time).toLocaleString()}
                </td>
                <td className="py-2 pr-3 text-xs text-muted-foreground">
                  {new Date(tr.exit_time).toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
