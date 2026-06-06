import { useEffect, useState, useCallback } from "react";
import { Loader2, Wifi, WifiOff, RefreshCw, Trash2, Save, Key } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type BrokerStatus, type BrokerInfo, type BrokerCredential } from "@/lib/api";

const FIELD_LABELS: Record<string, string> = {
  host: "Host",
  port: "Port",
  api_key: "API Key",
  secret_key: "Secret Key",
  passphrase: "Passphrase",
};

/** Multi-broker panel: exchange selector, API key config, connection test, positions/balance. */
export function BrokerPanel() {
  const { t } = useI18n();
  const [exchange, setExchange] = useState("futu");
  const [brokers, setBrokers] = useState<BrokerInfo[]>([]);
  const [credentials, setCredentials] = useState<BrokerCredential[]>([]);
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [positions, setPositions] = useState<Record<string, unknown>[]>([]);
  const [balance, setBalance] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state for current exchange
  const [form, setForm] = useState<Record<string, string>>({});
  const [testnet, setTestnet] = useState(true);

  // Load broker list + credentials on mount
  const loadMeta = useCallback(async () => {
    try {
      const [bl, cr] = await Promise.all([
        api.getBrokerList().catch(() => ({ brokers: [] })),
        api.getBrokerCredentials().catch(() => ({ credentials: [] })),
      ]);
      setBrokers(bl.brokers || []);
      setCredentials(cr.credentials || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  const currentBroker = brokers.find((b) => b.id === exchange);
  const savedCred = credentials.find((c) => c.exchange_id === exchange && c.is_active);

  // Load positions/balance/status for selected exchange
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (exchange === "futu") {
        const [s, a, p] = await Promise.all([
          api.getBrokerStatus().catch(() => null),
          api.getBrokerAccount().catch(() => null),
          api.getBrokerPositions().catch(() => null),
        ]);
        setStatus(s);
        if (a?.account) setBalance(a.account as Record<string, unknown>);
        else if (a?.available) setBalance({ available: true } as unknown as Record<string, unknown>);
        if (p?.positions) setPositions(p.positions);
      } else {
        const tn = savedCred?.testnet ?? true;
        const [s, p, b] = await Promise.all([
          api.testBrokerConnection({ exchange_id: exchange, testnet: tn }).catch(() => null),
          api.getBrokerPositionsMulti(exchange, tn).catch(() => ({ positions: [] })),
          api.getBrokerBalanceMulti(exchange, tn).catch(() => ({ balance: {} })),
        ]);
        setStatus(s);
        setPositions(p.positions || []);
        setBalance(b.balance || null);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [exchange, savedCred?.testnet]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Test connection
  const testConnection = async () => {
    setTesting(true);
    try {
      let result: BrokerStatus | null;
      if (exchange === "futu") {
        result = await api.getBrokerStatus();
      } else {
        result = await api.testBrokerConnection({ exchange_id: exchange, testnet });
      }
      setStatus(result);
    } catch { /* ignore */ }
    setTesting(false);
  };

  // Save credentials for non-Futu exchanges
  const saveCredentials = async () => {
    if (exchange === "futu") return;
    setSaving(true);
    try {
      await api.saveBrokerCredential({
        exchange_id: exchange,
        api_key: form.api_key || "",
        secret_key: form.secret_key || "",
        passphrase: form.passphrase || "",
        testnet,
      });
      await loadMeta();
    } catch { /* ignore */ }
    setSaving(false);
  };

  // Delete credentials
  const deleteCredentials = async () => {
    if (!savedCred) return;
    try {
      await api.deleteBrokerCredential(savedCred.id);
      setForm({});
      await loadMeta();
    } catch { /* ignore */ }
  };

  const connected = status?.connected ?? false;
  const posKeys = positions.length > 0 ? Object.keys(positions[0]) : [];

  return (
    <div className="flex flex-col h-full p-3 space-y-3 overflow-auto">
      {/* Exchange selector */}
      <div className="flex items-center gap-2">
        <select
          value={exchange}
          onChange={(e) => { setExchange(e.target.value); setForm({}); }}
          className="flex-1 input text-xs h-8"
        >
          {brokers.map((b) => (
            <option key={b.id} value={b.id}>{b.label}</option>
          ))}
        </select>
        <button
          onClick={testConnection}
          disabled={testing}
          className="p-1.5 rounded border text-muted-foreground hover:text-primary h-8 w-8 flex items-center justify-center"
          title={t.tradingNotifyTest || "Test"}
        >
          {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
        </button>
        <button
          onClick={fetchData}
          className="p-1.5 rounded border text-muted-foreground hover:text-primary h-8 w-8 flex items-center justify-center"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
        </button>
      </div>

      {/* Connection status */}
      <div className={cn(
        "flex items-center gap-2 p-2 rounded-lg border text-xs",
        connected ? "border-up/30 bg-up/5" : "border-down/30 bg-down/5"
      )}>
        {connected ? <Wifi className="h-3.5 w-3.5 text-up" /> : <WifiOff className="h-3.5 w-3.5 text-down" />}
        <span className={connected ? "text-up" : "text-down"}>
          {exchange === "futu"
            ? (connected ? (t.tradingBrokerConnected || "Futu Connected") : (t.tradingBrokerDisconnected || "Futu Disconnected"))
            : (connected ? `${currentBroker?.label || exchange} Connected` : `${currentBroker?.label || exchange} Disconnected`)}
        </span>
        {status?.error && <span className="text-down text-[10px] ml-auto truncate max-w-[120px]">{status.error}</span>}
      </div>

      {/* API Key config (non-Futu) */}
      {exchange !== "futu" && currentBroker && (
        <div className="border rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Key className="h-3 w-3" /> {t.settings || "Settings"}
            </div>
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={testnet}
                onChange={(e) => setTestnet(e.target.checked)}
                className="h-3 w-3"
              />
              Testnet
            </label>
          </div>
          {currentBroker.fields.map((field: string) => (
            <div key={field} className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground">{FIELD_LABELS[field] || field}</label>
              <input
                type="password"
                value={form[field] || ""}
                onChange={(e) => setForm((p) => ({ ...p, [field]: e.target.value }))}
                placeholder={savedCred ? "•••••••• (saved)" : `Enter ${FIELD_LABELS[field] || field}`}
                className="input text-xs h-7 w-full font-mono"
              />
            </div>
          ))}
          {currentBroker.note && (
            <div className="text-[10px] text-muted-foreground/60">{currentBroker.note}</div>
          )}
          <div className="flex gap-1.5">
            <button
              onClick={saveCredentials}
              disabled={saving}
              className="flex-1 flex items-center justify-center gap-1 h-7 text-[11px] rounded border hover:bg-muted disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
              {t.wfSave || "Save"}
            </button>
            {savedCred && (
              <button
                onClick={deleteCredentials}
                className="flex items-center justify-center gap-1 h-7 text-[11px] rounded border border-down/30 text-down hover:bg-down/5 px-2"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
      ) : (
        <>
          {/* Balance / Account */}
          {balance && (
            <div className="border rounded-lg p-3 space-y-1.5">
              <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                {t.tradingBrokerAccount || "Account"}
              </div>
              {Object.entries(balance).slice(0, 8).map(([k, v]) => (
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
              {t.tradingBrokerPositions || "Positions"} ({positions.length})
            </div>
            {positions.length === 0 ? (
              <div className="p-4 text-center text-[11px] text-muted-foreground/60">{t.ptNoPositions || "No positions"}</div>
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
