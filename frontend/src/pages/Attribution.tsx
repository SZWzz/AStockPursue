import { useState, useEffect, useCallback } from "react";
import { useI18n } from "@/lib/i18n";
import { useAttributionStore } from "@/stores/attributionStore";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { PieChart, BarChart3, TrendingUp, Calendar, Database } from "lucide-react";
import { BrinsonWaterfallChart } from "@/components/attribution/BrinsonWaterfallChart";
import { FactorExposureChart } from "@/components/attribution/FactorExposureChart";
import { SectorComparisonChart } from "@/components/attribution/SectorComparisonChart";

type TabKey = "brinson" | "factor" | "sector" | "decomp";

export function Attribution() {
  const { t } = useI18n();
  const store = useAttributionStore();
  const [activeTab, setActiveTab] = useState<TabKey>("brinson");
  const [runs, setRuns] = useState<Array<{ id: string; name?: string }>>([]);
  const [sectorClass, setSectorClass] = useState<string>("sw");

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
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold flex items-center gap-2"><PieChart className="h-5 w-5" />{t.attribution || "Performance Attribution"}</h1>
        {(store.fullReport as any)?.brinson?.data_source && (
          <span className={cn(
            "text-[10px] px-2 py-0.5 rounded-full border flex items-center gap-1",
            (store.fullReport as any).brinson.data_source !== "sample"
              ? "bg-emerald-500/10 text-up border-emerald-500/20"
              : "bg-amber-500/10 text-amber-600 border-amber-500/20"
          )}>
            <Database className="h-2.5 w-2.5" />
            {(store.fullReport as any).brinson.data_source === "sample" ? "Sample Data ⚠" : "Real Data"}
          </span>
        )}
      </div>

      {/* Run selector + classification */}
      <div className="flex items-center gap-3 text-sm flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-muted-foreground text-xs">{t.attributionSelectRun || "Run"}:</label>
          <select onChange={(e) => handleSelectRun(e.target.value)} value={store.selectedRunId || ""}
            className="border rounded px-2 py-1 bg-background text-sm min-w-[200px]">
            <option value="">-- Select --</option>
            {runs.map((r) => <option key={r.id} value={r.id}>{r.name || r.id}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-muted-foreground text-xs">Classification:</label>
          <select value={sectorClass} onChange={(e) => setSectorClass(e.target.value)}
            className="border rounded px-2 py-1 bg-background text-sm">
            <option value="sw">申万 (31 Sectors)</option>
            <option value="gics">GICS (11 Sectors)</option>
          </select>
        </div>
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
                <div className={cn("font-bold text-lg", (store.brinsonResult.allocation_effect as number) > 0 ? "text-up" : "text-down")}>
                  {(store.brinsonResult.allocation_effect as number)?.toFixed?.(4)}
                </div>
              </div>
              <div className="border rounded-lg p-3">
                <div className="text-muted-foreground text-xs">{t.attributionSelection || "Selection"}</div>
                <div className={cn("font-bold text-lg", (store.brinsonResult.selection_effect as number) > 0 ? "text-up" : "text-down")}>
                  {(store.brinsonResult.selection_effect as number)?.toFixed?.(4)}
                </div>
              </div>
              <div className="border rounded-lg p-3">
                <div className="text-muted-foreground text-xs">{t.attributionInteraction || "Interaction"}</div>
                <div className={cn("font-bold text-lg", (store.brinsonResult.interaction_effect as number) > 0 ? "text-up" : "text-down")}>
                  {(store.brinsonResult.interaction_effect as number)?.toFixed?.(4)}
                </div>
              </div>
              <div className="border rounded-lg p-3 bg-muted/20">
                <div className="text-muted-foreground text-xs">Total Excess</div>
                <div className={cn("font-bold text-lg", (store.brinsonResult.total_excess_return as number) > 0 ? "text-up" : "text-down")}>
                  {(store.brinsonResult.total_excess_return as number)?.toFixed?.(4)}
                </div>
              </div>
            </div>
            <BrinsonWaterfallChart
              perSector={(store.brinsonResult.per_sector as any[]) || []}
            />
          </div>
        )}

        {activeTab === "factor" && store.factorResult && (
          <div className="space-y-2">
            <FactorExposureChart
              betas={(store.factorResult.factor_betas as Record<string, number>) || {}}
              contributions={(store.factorResult.factor_contributions as Record<string, number>) || {}}
              rSquared={(store.factorResult.r_squared as number) || 0}
              residualReturn={(store.factorResult.residual_return as number) || 0}
            />
          </div>
        )}

        {activeTab === "sector" && store.sectorResult && (
          <SectorComparisonChart
            perSector={(store.sectorResult.per_sector as any[]) || []}
            concentrationHhi={(store.sectorResult.concentration_hhi as number) || 0}
          />
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
