import { useState, useEffect, useCallback } from "react";
import { useI18n } from "@/lib/i18n";
import { useAttributionStore } from "@/stores/attributionStore";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { PieChart, BarChart3, TrendingUp, Calendar } from "lucide-react";

type TabKey = "brinson" | "factor" | "sector" | "decomp";

export function Attribution() {
  const { t } = useI18n();
  const store = useAttributionStore();
  const [activeTab, setActiveTab] = useState<TabKey>("brinson");
  const [runs, setRuns] = useState<Array<{ id: string; name?: string }>>([]);

  useEffect(() => {
    (api as any).listRuns?.().then((d: any) => {
      if (Array.isArray(d)) setRuns(d.map((r: any) => ({ id: r.id || r.run_id, name: r.title || r.id })));
    }).catch(() => {});
  }, []);

  const handleSelectRun = useCallback((id: string) => {
    store.setRunId(id);
    store.computeFull();
  }, [store]);

  const tabs: { key: TabKey; label: string; icon: typeof PieChart }[] = [
    { key: "brinson", label: "Brinson", icon: PieChart },
    { key: "factor", label: t.factor || "Factor", icon: BarChart3 },
    { key: "sector", label: t.sector || "Sector", icon: TrendingUp },
    { key: "decomp", label: t.decomp || "Decomposition", icon: Calendar },
  ];

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <h1 className="text-lg font-bold flex items-center gap-2"><PieChart className="h-5 w-5" />{t.attribution || "Performance Attribution"}</h1>

      {/* Run selector */}
      <div className="flex items-center gap-2 text-sm">
        <label className="text-muted-foreground">{t.attributionSelectRun || "Select Run"}:</label>
        <select onChange={(e) => handleSelectRun(e.target.value)} value={store.selectedRunId || ""}
          className="border rounded px-2 py-1 bg-background text-sm min-w-[200px]">
          <option value="">-- {t.attributionSelectRun || "Select a run"} --</option>
          {runs.map((r) => <option key={r.id} value={r.id}>{r.name || r.id}</option>)}
        </select>
        {store.loading && <span className="text-xs text-muted-foreground animate-pulse">Computing...</span>}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {tabs.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={cn("flex items-center gap-1 px-3 py-1.5 text-xs rounded-t transition",
              activeTab === tab.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
            <tab.icon className="h-3.5 w-3.5" />{tab.label}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 border rounded-xl p-3 overflow-auto">
        {!store.selectedRunId && (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            {t.attributionNoRun || "Select a completed backtest run to analyze"}
          </div>
        )}

        {activeTab === "brinson" && store.brinsonResult && (
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-3 text-center text-sm">
              <div className="border rounded-lg p-3">
                <div className="text-muted-foreground text-xs">{t.attributionAllocation || "Allocation"}</div>
                <div className={cn("font-bold", (store.brinsonResult.allocation_effect as number) > 0 ? "text-success" : "text-destructive")}>
                  {(store.brinsonResult.allocation_effect as number)?.toFixed?.(4)}
                </div>
              </div>
              <div className="border rounded-lg p-3">
                <div className="text-muted-foreground text-xs">{t.attributionSelection || "Selection"}</div>
                <div className={cn("font-bold", (store.brinsonResult.selection_effect as number) > 0 ? "text-success" : "text-destructive")}>
                  {(store.brinsonResult.selection_effect as number)?.toFixed?.(4)}
                </div>
              </div>
              <div className="border rounded-lg p-3">
                <div className="text-muted-foreground text-xs">{t.attributionInteraction || "Interaction"}</div>
                <div className={cn("font-bold", (store.brinsonResult.interaction_effect as number) > 0 ? "text-success" : "text-destructive")}>
                  {(store.brinsonResult.interaction_effect as number)?.toFixed?.(4)}
                </div>
              </div>
              <div className="border rounded-lg p-3 bg-muted/20">
                <div className="text-muted-foreground text-xs">Total Excess</div>
                <div className="font-bold">{(store.brinsonResult.total_excess_return as number)?.toFixed?.(4)}</div>
              </div>
            </div>
            <table className="w-full text-xs">
              <thead><tr className="border-b text-muted-foreground">
                <th className="text-left py-1">Sector</th>
                <th className="text-right py-1">Allocation</th>
                <th className="text-right py-1">Selection</th>
                <th className="text-right py-1">Interaction</th>
                <th className="text-right py-1">Total</th>
              </tr></thead>
              <tbody>
                {(store.brinsonResult.per_sector as any[])?.map((s: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="py-1">{s.sector}</td>
                    <td className={cn("text-right", s.allocation_effect > 0 ? "text-success" : "text-destructive")}>{s.allocation_effect?.toFixed(4)}</td>
                    <td className={cn("text-right", s.selection_effect > 0 ? "text-success" : "text-destructive")}>{s.selection_effect?.toFixed(4)}</td>
                    <td className="text-right">{s.interaction_effect?.toFixed(4)}</td>
                    <td className={cn("text-right font-medium", s.total > 0 ? "text-success" : "text-destructive")}>{s.total?.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "factor" && store.factorResult && (
          <div className="space-y-2">
            <div className="text-sm">R² = {(store.factorResult.r_squared as number)?.toFixed?.(4)} | Residual Return: {(store.factorResult.residual_return as number)?.toFixed?.(6)}</div>
            <table className="w-full text-xs">
              <thead><tr className="border-b text-muted-foreground">
                <th className="text-left py-1">Factor</th><th className="text-right py-1">Beta</th><th className="text-right py-1">Contribution</th>
              </tr></thead>
              <tbody>
                {Object.entries(store.factorResult.factor_betas as Record<string, number> || {}).map(([k, beta]) => (
                  <tr key={k} className="border-b hover:bg-muted/30">
                    <td className="py-1 font-mono text-[11px]">{k}</td>
                    <td className="text-right">{beta?.toFixed(4)}</td>
                    <td className={cn("text-right", (((store.factorResult?.factor_contributions as any)?.[k] || 0) > 0) ? "text-success" : "text-destructive")}>
                      {(store.factorResult?.factor_contributions as any)?.[k]?.toFixed?.(6)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "sector" && store.sectorResult && (
          <div className="space-y-2">
            <div className="text-xs text-muted-foreground">Concentration HHI: {(store.sectorResult.concentration_hhi as number)?.toFixed?.(4)}</div>
            <table className="w-full text-xs">
              <thead><tr className="border-b text-muted-foreground">
                <th className="text-left py-1">Sector</th><th className="text-right py-1">Weight</th><th className="text-right py-1">P&L</th><th className="text-right py-1">Contribution</th>
              </tr></thead>
              <tbody>
                {(store.sectorResult.per_sector as any[])?.map((s: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="py-1">{s.sector}</td>
                    <td className="text-right">{(s.weight * 100).toFixed(1)}%</td>
                    <td className={cn("text-right", s.pnl > 0 ? "text-success" : "text-destructive")}>{s.pnl?.toFixed(4)}</td>
                    <td className={cn("text-right", s.contribution > 0 ? "text-success" : "text-destructive")}>{s.contribution?.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "decomp" && store.decompResult && (
          <div className="text-xs space-y-2">
            <div className="grid grid-cols-4 gap-2">
              {["observed", "trend", "seasonal", "residual"].map((k) => {
                const vals = (store.decompResult as any)?.[k] as number[] | undefined;
                const last = vals?.[vals.length - 1] ?? 0;
                return (
                  <div key={k} className="border rounded-lg p-3 text-center">
                    <div className="text-muted-foreground text-[10px]">{k}</div>
                    <div className={cn("font-bold text-sm", last > 0 ? "text-success" : "text-destructive")}>{last?.toFixed?.(6)}</div>
                  </div>
                );
              })}
            </div>
            <div className="text-muted-foreground">{store.decompResult.dates ? `${(store.decompResult.dates as string[]).length} data points` : ""}</div>
          </div>
        )}
      </div>
    </div>
  );
}
