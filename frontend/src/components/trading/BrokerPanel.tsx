import { useEffect, useState, useCallback } from "react";
import { Loader2, Wifi, WifiOff, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type BrokerStatus } from "@/lib/api";

/** Broker connection status indicator + account info + positions table. */
export function BrokerPanel() {
  const { t } = useI18n();
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [account, setAccount] = useState<Record<string, unknown> | null>(null);
  const [positions, setPositions] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, a, p] = await Promise.all([
        api.getBrokerStatus().catch(() => null),
        api.getBrokerAccount().catch(() => null),
        api.getBrokerPositions().catch(() => null),
      ]);
      setStatus(s);
      if (a?.available && a.account) setAccount(a.account as Record<string, unknown>);
      if (p?.positions) setPositions(p.positions);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const connected = status?.connected ?? false;
  const posKeys = positions.length > 0 ? Object.keys(positions[0]) : [];

  return (
    <div className="flex flex-col h-full p-3 space-y-3 overflow-auto">
      {/* Connection status */}
      <div className={cn(
        "flex items-center gap-2 p-2 rounded-lg border text-xs",
        connected ? "border-up/30 bg-up/5" : "border-down/30 bg-down/5"
      )}>
        {connected ? <Wifi className="h-3.5 w-3.5 text-up" /> : <WifiOff className="h-3.5 w-3.5 text-down" />}
        <span className={connected ? "text-up" : "text-down"}>
          {connected ? (t.tradingBrokerConnected || "富途已连接") : (t.tradingBrokerDisconnected || "富途未连接")}
        </span>
        {status?.host && <span className="text-muted-foreground ml-auto font-mono">{status.host}:{status.port}</span>}
        <button onClick={fetchAll} className="p-0.5 text-muted-foreground hover:text-primary">
          <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
      ) : (
        <>
          {/* Account info */}
          {account && (
            <div className="border rounded-lg p-3 space-y-1.5">
              <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t.tradingBrokerAccount || "账户"}</div>
              {Object.entries(account).slice(0, 8).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="font-mono font-medium">{String(v ?? "—")}</span>
                </div>
              ))}
            </div>
          )}

          {/* Positions */}
          <div className="border rounded-lg overflow-hidden">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2 border-b">
              {t.tradingBrokerPositions || "持仓"} ({positions.length})
            </div>
            {positions.length === 0 ? (
              <div className="p-4 text-center text-[11px] text-muted-foreground/60">无持仓</div>
            ) : (
              <div className="overflow-auto max-h-64">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b bg-muted/30">
                      {posKeys.slice(0, 6).map((k) => (
                        <th key={k} className="px-2 py-1.5 text-left font-medium text-muted-foreground">{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos, i) => (
                      <tr key={i} className="border-b border-border/20 hover:bg-muted/30">
                        {posKeys.slice(0, 6).map((k) => (
                          <td key={k} className="px-2 py-1.5 font-mono">{String(pos[k] ?? "—")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
