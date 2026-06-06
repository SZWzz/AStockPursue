import { useEffect, useState } from "react";
import { Activity, CheckCircle, XCircle, AlertTriangle, RefreshCw, Database, Zap, Eye, EyeOff, Trash2, Wifi } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DataSourceLoaderStatus } from "@/types/api";

const MARKET_I18N_KEYS: Record<string, string> = {
  a_share: "wfEnum_equity_cn", us_equity: "wfEnum_equity_us", hk_equity: "wfEnum_equity_hk",
  crypto: "wfEnum_crypto", futures: "wfEnum_CN_FUTURES", fund: "wfEnum_fund",
  macro: "wfEnum_macro", forex: "wfEnum_FOREX", index: "wfEnum_index",
  commodity: "wfEnum_commodity",
};

function marketLabel(t: Record<string, string>, market: string): string {
  const key = MARKET_I18N_KEYS[market];
  return key && (t as any)[key] ? (t as any)[key] : market;
}

const AUTH_SOURCE_NAMES = ["tushare", "twelvedata", "finnhub", "futu"];

export default function DataSourceStatus() {
  const { t } = useI18n();
  const [sources, setSources] = useState<DataSourceLoaderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastCheck, setLastCheck] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; msg: string }>>({});
  const [clearing, setClearing] = useState<Record<string, boolean>>({});

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await api.getDataSourceStatus();
      if (res?.loaders) setSources(res.loaders);
      else if (Array.isArray(res)) setSources(res);
      setLastCheck(new Date().toLocaleTimeString());
    } catch (e) {
      console.warn("Failed to fetch data source status", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const toggleExpand = (name: string) => {
    setExpanded(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const handleTest = async (name: string) => {
    setTesting(prev => ({ ...prev, [name]: true }));
    try {
      const key = keys[name] || "";
      const res = await fetch(`/api/v1/data-sources/${name}/test?api_key=${encodeURIComponent(key)}`, { method: "POST" });
      const data = await res.json();
      setTestResults(prev => ({ ...prev, [name]: { ok: res.ok, msg: data.message || data.error || (res.ok ? t.dsConnectionOk : t.dsConnectionFailed) } }));
    } catch (e: any) {
      setTestResults(prev => ({ ...prev, [name]: { ok: false, msg: e.message || t.dsConnectionFailed } }));
    } finally {
      setTesting(prev => ({ ...prev, [name]: false }));
    }
  };

  const handleSaveKey = async (name: string) => {
    try {
      await fetch("/api/auth/data-source-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: name, api_key: keys[name] || "" }),
      });
    } catch (e) {
      console.warn("Failed to save key", e);
    }
  };

  const handleClearCache = async (name: string) => {
    setClearing(prev => ({ ...prev, [name]: true }));
    try {
      await fetch(`/api/v1/data-sources/${name}/clear-cache`, { method: "POST" });
    } catch (e) {
      console.warn("Failed to clear cache", e);
    } finally {
      setClearing(prev => ({ ...prev, [name]: false }));
    }
  };

  const grouped: Record<string, DataSourceLoaderStatus[]> = {};
  for (const s of sources) {
    const m = s.markets?.[0] || "other";
    if (!grouped[m]) grouped[m] = [];
    grouped[m].push(s);
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">{t.dsTitle}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t.dsSubtitle}
            {lastCheck && <span className="ml-2">· {t.dsLastCheck}: {lastCheck}</span>}
          </p>
        </div>
        <button onClick={fetchStatus} disabled={loading}
          className="px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm flex items-center gap-1.5 hover:opacity-90 disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          {t.dsRefresh}
        </button>
      </div>

      {loading && sources.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Activity className="w-8 h-8 mx-auto mb-2 animate-pulse" />
          {t.dsLoading}
        </div>
      ) : (
        Object.entries(grouped).map(([market, loaders]) => (
          <div key={market} className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-4 h-4 text-primary" />
              <h2 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">
                {marketLabel(t, market)}
              </h2>
              <span className="text-xs text-muted-foreground">({loaders.length})</span>
            </div>
            <div className="space-y-2">
              {loaders.map((l) => {
                const isExpanded = expanded[l.name] || false;
                const needsAuth = l.requires_auth || AUTH_SOURCE_NAMES.includes(l.name);
                return (
                  <div key={l.name}>
                    <div
                      className="flex items-center justify-between bg-card border rounded-lg px-4 py-3 hover:bg-accent/30 transition-colors cursor-pointer"
                      onClick={() => toggleExpand(l.name)}
                    >
                      <div className="flex items-center gap-3">
                        {l.available ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : needsAuth ? (
                          <AlertTriangle className="w-4 h-4 text-amber-500" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-400" />
                        )}
                        <div>
                          <span className="font-medium text-sm">{l.display || l.name}</span>
                          <span className="text-xs text-muted-foreground ml-2 font-mono">{l.name}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        {needsAuth && (
                          <span className="px-2 py-0.5 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 rounded-full">
                            {t.dsAuthRequired}
                          </span>
                        )}
                        <span className={`px-2 py-0.5 rounded-full ${
                          l.available
                            ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                            : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                        }`}>
                          {l.available ? t.dsAvailable : t.dsUnavailable}
                        </span>
                      </div>
                    </div>

                    {/* Expandable config panel */}
                    {isExpanded && (
                      <div className="border border-t-0 rounded-b-lg px-4 py-3 bg-muted/30 space-y-3">
                        {/* API Key for sources that need auth */}
                        {needsAuth && (
                          <div>
                            <label className="text-xs font-medium text-muted-foreground">{t.dsApiKey}</label>
                            <div className="flex gap-2 mt-1">
                              <div className="relative flex-1">
                                <input
                                  type={showKey[l.name] ? "text" : "password"}
                                  value={keys[l.name] || ""}
                                  onChange={e => setKeys(prev => ({ ...prev, [l.name]: e.target.value }))}
                                  placeholder={t.dsEnterKey}
                                  className="w-full text-xs px-3 py-1.5 border rounded-lg bg-background"
                                  onClick={e => e.stopPropagation()}
                                />
                                <button
                                  onClick={e => { e.stopPropagation(); setShowKey(prev => ({ ...prev, [l.name]: !prev[l.name] })); }}
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                                >
                                  {showKey[l.name] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                              <button
                                onClick={e => { e.stopPropagation(); handleSaveKey(l.name); }}
                                className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs"
                              >
                                {t.dsSave}
                              </button>
                            </div>
                            {AUTH_SOURCE_NAMES.includes(l.name) && (
                              <p className="text-[10px] text-muted-foreground mt-1">
                                {l.name === "tushare" && "Register at tushare.pro →"}
                                {l.name === "twelvedata" && "Register at twelvedata.com →"}
                                {l.name === "finnhub" && "Register at finnhub.io →"}
                                {l.name === "futu" && "Requires FutuOpenD running locally"}
                              </p>
                            )}
                          </div>
                        )}

                        {/* Test connection result */}
                        {testResults[l.name] && (
                          <div className={`text-xs px-3 py-1.5 rounded-lg ${testResults[l.name].ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                            {testResults[l.name].ok ? "✅ " : "❌ "}{testResults[l.name].msg}
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex gap-2">
                          <button
                            onClick={e => { e.stopPropagation(); handleTest(l.name); }}
                            disabled={testing[l.name]}
                            className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-xs hover:bg-accent disabled:opacity-50"
                          >
                            <Wifi className="w-3 h-3" />
                            {testing[l.name] ? t.dsTesting : t.dsTestConnection}
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); handleClearCache(l.name); }}
                            disabled={clearing[l.name]}
                            className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-xs hover:bg-accent disabled:opacity-50 text-red-600"
                          >
                            <Trash2 className="w-3 h-3" />
                            {clearing[l.name] ? t.dsClearing : t.dsClearCache}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))
      )}

      {!loading && sources.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <Zap className="w-8 h-8 mx-auto mb-2" />
          {t.dsNoData}
        </div>
      )}
    </div>
  );
}
