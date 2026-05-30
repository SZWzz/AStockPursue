import { useEffect, useState } from "react";
import { Activity, CheckCircle, XCircle, AlertTriangle, RefreshCw, Database, Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { DataSourceLoaderStatus } from "@/types/api";

const MARKET_LABELS: Record<string, string> = {
  a_share: "A股",
  us_equity: "美股",
  hk_equity: "港股",
  crypto: "加密",
  futures: "期货",
  fund: "基金",
  macro: "宏观",
  forex: "外汇",
  index: "指数",
  commodity: "商品",
};

export default function DataSourceStatus() {
  const [sources, setSources] = useState<DataSourceLoaderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastCheck, setLastCheck] = useState("");

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await api.getDataSourceStatus();
      if (res?.loaders) {
        setSources(res.loaders);
      } else if (Array.isArray(res)) {
        setSources(res);
      }
      setLastCheck(new Date().toLocaleTimeString());
    } catch (e) {
      console.warn("Failed to fetch data source status", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

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
          <h1 className="text-xl font-bold">数据源状态</h1>
          <p className="text-sm text-muted-foreground mt-1">
            显示所有已注册数据加载器的可用状态
            {lastCheck && <span className="ml-2">· 最后检查: {lastCheck}</span>}
          </p>
        </div>
        <button
          onClick={fetchStatus}
          disabled={loading}
          className="px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm flex items-center gap-1.5 hover:opacity-90 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          刷新
        </button>
      </div>

      {loading && sources.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Activity className="w-8 h-8 mx-auto mb-2 animate-pulse" />
          加载中...
        </div>
      ) : (
        Object.entries(grouped).map(([market, loaders]) => (
          <div key={market} className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-4 h-4 text-primary" />
              <h2 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">
                {MARKET_LABELS[market] || market}
              </h2>
              <span className="text-xs text-muted-foreground">({loaders.length})</span>
            </div>
            <div className="space-y-1.5">
              {loaders.map((l) => (
                <div
                  key={l.name}
                  className="flex items-center justify-between bg-card border rounded-lg px-4 py-3 hover:bg-accent/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {l.available ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : l.requires_auth ? (
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400" />
                    )}
                    <div>
                      <span className="font-medium text-sm">{l.display || l.name}</span>
                      <span className="text-xs text-muted-foreground ml-2 font-mono">{l.name}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    {l.requires_auth && (
                      <span className="px-2 py-0.5 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 rounded-full">
                        需认证
                      </span>
                    )}
                    <span className={`px-2 py-0.5 rounded-full ${
                      l.available
                        ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    }`}>
                      {l.available ? "可用" : "不可用"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}

      {!loading && sources.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <Zap className="w-8 h-8 mx-auto mb-2" />
          暂无数据源信息。请确保后端 API 正常连接。
        </div>
      )}
    </div>
  );
}
