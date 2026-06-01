import { useState, useEffect, useCallback, useMemo } from "react";
import { useI18n } from "@/lib/i18n";
import { useFactorMiningStore } from "@/stores/factorMiningStore";
import { EvolutionChart } from "@/components/factor-mining/EvolutionChart";
import { ExpressionTreeViewer } from "@/components/factor-mining/ExpressionTreeViewer";
import { CandidatesTable } from "@/components/factor-mining/CandidatesTable";
import { MiningProgressCard } from "@/components/factor-mining/MiningProgressCard";
import { LiveBestFactor } from "@/components/factor-mining/LiveBestFactor";
import { FitnessDistributionChart } from "@/components/factor-mining/FitnessDistributionChart";
import { EliteTrackerPanel } from "@/components/factor-mining/EliteTrackerPanel";
import { GenerationLogTable } from "@/components/factor-mining/GenerationLogTable";
import { ICDecayCurve } from "@/components/factor-mining/ICDecayCurve";
import { RunComparisonView } from "@/components/factor-mining/RunComparisonView";
import { LineageTree } from "@/components/factor-mining/LineageTree";
import { cn } from "@/lib/utils";
import { Zap, FlaskConical, HelpCircle } from "lucide-react";

type TabKey = "gp" | "llm" | "hybrid" | "candidates" | "history" | "compare";

// ── GP Config Presets (Phase C P0) ─────────────────────────────────
const GP_PRESETS = [
  {
    key: "quick",
    label: "Quick Explore",
    icon: "⚡",
    desc: "Fast discovery, 10 gens, composite fitness",
    config: {
      population_size: 50,
      generations: 10,
      tournament_size: 5,
      crossover_prob: 0.7,
      mutation_prob: 0.25,
      fitness_metric: "composite" as const,
      complexity_penalty: "bic" as const,
      use_tiered_operators: true,
      use_hybrid_init: true,
      use_kb: true,
      train_start: "2024-01-01",
      train_end: "2024-12-31",
      test_start: "2025-01-01",
      test_end: "2025-06-30",
    },
  },
  {
    key: "standard",
    label: "Standard",
    icon: "🧬",
    desc: "Balanced evolution, 30 gens, composite + KB",
    config: {
      population_size: 100,
      generations: 30,
      tournament_size: 7,
      crossover_prob: 0.7,
      mutation_prob: 0.2,
      fitness_metric: "composite" as const,
      complexity_penalty: "bic" as const,
      use_tiered_operators: true,
      use_hybrid_init: true,
      use_kb: true,
      train_start: "2023-01-01",
      train_end: "2024-12-31",
      test_start: "2025-01-01",
      test_end: "2025-12-31",
    },
  },
  {
    key: "deep",
    label: "Deep Search",
    icon: "🔬",
    desc: "Thorough exploration, 100 gens, composite + tiers",
    config: {
      population_size: 200,
      generations: 100,
      tournament_size: 10,
      crossover_prob: 0.65,
      mutation_prob: 0.15,
      fitness_metric: "composite" as const,
      complexity_penalty: "bic" as const,
      use_tiered_operators: true,
      use_hybrid_init: true,
      use_kb: true,
      fdr_alpha: 0.05,
      train_start: "2020-01-01",
      train_end: "2024-12-31",
      test_start: "2025-01-01",
      test_end: "2025-12-31",
    },
  },
] as const;

const PARAM_TOOLTIPS: Record<string, string> = {
  population_size: "Number of factor expressions in each generation. Larger = more diversity but slower.",
  generations: "Number of evolution cycles. More generations = deeper search but diminishing returns.",
  tournament_size: "Number of individuals competing in each selection round. Higher = stronger selection pressure.",
  crossover_prob: "Probability of combining two parent factors to create offspring. Higher = more recombination.",
  mutation_prob: "Probability of randomly altering a factor. Higher = more exploration, lower = more exploitation.",
  fitness_metric: "ic_mean = Pearson IC, rank_ic = Spearman IC (robust), sharpe = long-short portfolio Sharpe.",
  complexity_penalty: "aic = 2×nodes, bic = nodes×ln(n) (stronger preference for simplicity), none = no penalty.",
};

export function FactorMining() {
  const { t } = useI18n();
  const store = useFactorMiningStore();
  const [activeTab, setActiveTab] = useState<TabKey>("gp");

  // GP config state (Phase C P0: composite fitness, tiers, hybrid init, KB)
  const [gpConfig, setGpConfig] = useState({
    population_size: 100,
    generations: 30,
    tournament_size: 7,
    crossover_prob: 0.7,
    mutation_prob: 0.2,
    fitness_metric: "composite" as "composite" | "ic_mean" | "rank_ic" | "sharpe",
    complexity_penalty: "bic" as "aic" | "bic" | "none",
    use_tiered_operators: true,
    use_hybrid_init: true,
    use_kb: true,
    fdr_alpha: 0.05,
    train_start: "2023-01-01",
    train_end: "2024-12-31",
    test_start: "2025-01-01",
    test_end: "2025-12-31",
    universe: [] as string[],
  });

  // LLM state
  const [llmText, setLlmText] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Validate modal
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<any>(null);

  // Active preset tracking
  const [activePreset, setActivePreset] = useState<string>("standard");

  useEffect(() => {
    store.fetchCandidates();
    store.fetchMiningHistory();
    return () => {
      store.unsubscribeFromJob();
    };
  }, []);

  // Derived: current best factor from latest generation
  const latestGen = useMemo(() => {
    if (store.gpGenerations.length === 0) return null;
    return store.gpGenerations[store.gpGenerations.length - 1];
  }, [store.gpGenerations]);

  const applyPreset = useCallback((presetKey: string) => {
    const preset = GP_PRESETS.find((p) => p.key === presetKey);
    if (preset) {
      setGpConfig((prev) => ({ ...prev, ...preset.config }));
      setActivePreset(presetKey);
    }
  }, []);

  const handleStartGp = useCallback(async () => {
    try {
      await store.startGpRun(gpConfig);
    } catch {
      // handled by store
    }
  }, [gpConfig, store]);

  const handleValidation = useCallback(async (id: string) => {
    setSelectedCandidate(id);
    try {
      const result = await store.validateCandidate(id);
      setValidationResult(result);
    } catch {
      setValidationResult(null);
    }
  }, [store]);

  const tabs: { key: TabKey; label: string }[] = [
    { key: "gp", label: t.fmTabGp },
    { key: "llm", label: t.fmTabLlm },
    { key: "hybrid", label: t.fmTabHybrid },
    { key: "candidates", label: t.fmTabCandidates },
    { key: "history", label: t.fmTabHistory },
    { key: "compare", label: "Compare" },
  ];

  const isRunning = store.gpStatus === "running" || store.gpStatus === "starting";

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      <div className="flex items-center gap-2">
        <h1 className="text-lg font-bold">🧬 {t.factorMining || "AI Factor Mining"}</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b pb-0">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-4 py-2 text-sm rounded-t transition",
              activeTab === tab.key
                ? "bg-primary text-primary-foreground font-medium"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════════
          GP Evolution Tab — Three-column cockpit layout
          ════════════════════════════════════════════════════════════ */}
      {activeTab === "gp" && (
        <div className="flex gap-3 flex-1 min-h-0">
          {/* ── Left: Config Panel ── */}
          <div className="w-72 flex-shrink-0 border rounded-xl flex flex-col overflow-hidden">
            <div className="p-3 border-b bg-muted/30">
              <h3 className="font-semibold text-sm flex items-center gap-1.5">
                <FlaskConical className="h-4 w-4" />
                {t.fmGpSetup || "GP Setup"}
              </h3>
            </div>
            <div className="p-3 space-y-3 overflow-y-auto flex-1">
              {/* Presets */}
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Presets</label>
                <div className="grid grid-cols-3 gap-1">
                  {GP_PRESETS.map((preset) => (
                    <button
                      key={preset.key}
                      onClick={() => applyPreset(preset.key)}
                      disabled={isRunning}
                      className={cn(
                        "px-2 py-1.5 rounded text-xs text-center transition border",
                        activePreset === preset.key
                          ? "bg-primary/10 border-primary/30 text-primary font-medium"
                          : "border-border hover:bg-muted/50 text-muted-foreground",
                        isRunning && "opacity-50 cursor-not-allowed"
                      )}
                      title={preset.desc}
                    >
                      <div className="text-sm">{preset.icon}</div>
                      <div>{preset.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Parameters */}
              {[
                { key: "population_size", label: t.fmPopulationSize || "Population", min: 10, max: 500 },
                { key: "generations", label: t.fmGenerations || "Generations", min: 5, max: 200 },
                { key: "tournament_size", label: "Tournament Size", min: 2, max: 20 },
                { key: "crossover_prob", label: "Crossover Rate", min: 0, max: 1, step: 0.05 },
                { key: "mutation_prob", label: "Mutation Rate", min: 0, max: 1, step: 0.05 },
              ].map((param) => (
                <div key={param.key} className="space-y-1">
                  <div className="flex items-center gap-1">
                    <label className="text-xs text-muted-foreground">{param.label}</label>
                    <span className="group relative">
                      <HelpCircle className="h-3 w-3 text-muted-foreground/50 cursor-help" />
                      <span className="hidden group-hover:block absolute left-0 bottom-full mb-1 w-48 p-2 bg-popover border rounded text-[10px] text-muted-foreground z-50 shadow-lg">
                        {PARAM_TOOLTIPS[param.key] || ""}
                      </span>
                    </span>
                  </div>
                  <input
                    type="number"
                    value={gpConfig[param.key as keyof typeof gpConfig] as number}
                    onChange={(e) => setGpConfig({ ...gpConfig, [param.key]: +e.target.value })}
                    className="w-full rounded border bg-background px-2 py-1 text-sm"
                    min={param.min}
                    max={param.max}
                    step={(param as any).step || 1}
                    disabled={isRunning}
                  />
                </div>
              ))}

              {/* Fitness metric */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Fitness Metric</label>
                <select
                  value={gpConfig.fitness_metric}
                  onChange={(e) => setGpConfig({ ...gpConfig, fitness_metric: e.target.value as any })}
                  className="w-full rounded border bg-background px-2 py-1 text-sm"
                  disabled={isRunning}
                >
                  <option value="ic_mean">IC Mean (Pearson)</option>
                  <option value="rank_ic">Rank IC (Spearman)</option>
                  <option value="sharpe">Long-Short Sharpe</option>
                </select>
              </div>

              {/* Complexity penalty */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Complexity Penalty</label>
                <select
                  value={gpConfig.complexity_penalty}
                  onChange={(e) => setGpConfig({ ...gpConfig, complexity_penalty: e.target.value as any })}
                  className="w-full rounded border bg-background px-2 py-1 text-sm"
                  disabled={isRunning}
                >
                  <option value="bic">BIC (prefer simple)</option>
                  <option value="aic">AIC (moderate)</option>
                  <option value="none">None</option>
                </select>
              </div>

              {/* Date range */}
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t.fmTrainStart || "Train Start"}</label>
                  <input
                    type="text"
                    value={gpConfig.train_start}
                    onChange={(e) => setGpConfig({ ...gpConfig, train_start: e.target.value })}
                    className="w-full rounded border bg-background px-2 py-1 text-sm"
                    disabled={isRunning}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t.fmTrainEnd || "Train End"}</label>
                  <input
                    type="text"
                    value={gpConfig.train_end}
                    onChange={(e) => setGpConfig({ ...gpConfig, train_end: e.target.value })}
                    className="w-full rounded border bg-background px-2 py-1 text-sm"
                    disabled={isRunning}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t.fmTestStart || "Test Start"}</label>
                  <input
                    type="text"
                    value={gpConfig.test_start}
                    onChange={(e) => setGpConfig({ ...gpConfig, test_start: e.target.value })}
                    className="w-full rounded border bg-background px-2 py-1 text-sm"
                    disabled={isRunning}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t.fmTestEnd || "Test End"}</label>
                  <input
                    type="text"
                    value={gpConfig.test_end}
                    onChange={(e) => setGpConfig({ ...gpConfig, test_end: e.target.value })}
                    className="w-full rounded border bg-background px-2 py-1 text-sm"
                    disabled={isRunning}
                  />
                </div>
              </div>

              {/* Start / Cancel buttons */}
              <button
                onClick={handleStartGp}
                disabled={isRunning}
                className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm font-medium disabled:opacity-50 transition"
              >
                {store.gpStatus === "running" ? t.fmRunning || "Running..."
                  : store.gpStatus === "starting" ? t.fmStarting || "Starting..."
                    : t.fmStartGp || "Start Evolution"}
              </button>

              {store.gpStatus === "running" && (
                <button
                  onClick={store.cancelGpRun}
                  className="w-full px-3 py-1 bg-destructive/10 text-destructive rounded text-sm hover:bg-destructive/20 transition"
                >
                  {t.fmStop || "Stop"}
                </button>
              )}
            </div>
          </div>

          {/* ── Center: Charts ── */}
          <div className="flex-1 flex flex-col gap-3 min-w-0 overflow-y-auto">
            {/* Progress card */}
            <MiningProgressCard
              status={store.gpStatus}
              currentGeneration={store.gpGenerations.length}
              totalGenerations={gpConfig.generations}
              bestIC={latestGen?.best_ic || 0}
              dataSource={store.gpDataSource}
              dataSourceDetail={store.gpDataSourceDetail}
            />

            {/* Evolution chart */}
            <EvolutionChart generations={store.gpGenerations} />

            {/* Fitness distribution chart */}
            <FitnessDistributionChart
              distribution={latestGen?.fitness_distribution}
            />

            {/* Best factor at end of run */}
            {store.gpResult?.result?.best_individuals?.[0] && (
              <div className="border rounded-xl p-3">
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                  <Zap className="h-4 w-4 text-amber-500" />
                  {t.fmBestFactor || "Best Discovered Factor"}
                </h3>
                <p className="text-xs font-mono bg-muted/50 p-2 rounded break-all">
                  {store.gpResult.result.best_individuals[0].formula}
                </p>
                {store.gpResult.result.best_individuals[0].expression_json && (
                  <ExpressionTreeViewer
                    tree={store.gpResult.result.best_individuals[0].expression_json as any}
                  />
                )}
                <div className="grid grid-cols-4 gap-2 mt-2 text-xs">
                  <div className="text-center border rounded p-1.5">
                    <div className="text-muted-foreground">Train IC</div>
                    <div className="font-mono font-medium">
                      {(store.gpResult.result.best_individuals[0].train_ic || 0).toFixed(4)}
                    </div>
                  </div>
                  <div className="text-center border rounded p-1.5">
                    <div className="text-muted-foreground">Test IC</div>
                    <div className="font-mono font-medium">
                      {(store.gpResult.result.best_individuals[0].test_ic || 0).toFixed(4)}
                    </div>
                  </div>
                  <div className="text-center border rounded p-1.5">
                    <div className="text-muted-foreground">IR</div>
                    <div className="font-mono font-medium">
                      {(store.gpResult.result.best_individuals[0].test_ir || 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center border rounded p-1.5">
                    <div className="text-muted-foreground">Complexity</div>
                    <div className="font-mono font-medium">
                      {store.gpResult.result.best_individuals[0].complexity || 0}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* IC Decay Curve (when best factor available) */}
            {store.gpResult?.result?.best_individuals?.[0] && (
              <ICDecayCurve
                data={(store.gpResult.result as any)?.ic_decay}
              />
            )}

            {/* Generation log table */}
            <GenerationLogTable generations={store.gpGenerations} />
          </div>

          {/* ── Right: Live insights ── */}
          <div className="w-72 flex-shrink-0 flex flex-col gap-3 overflow-y-auto">
            {/* Live best factor (updates each generation) */}
            <LiveBestFactor
              formula={latestGen?.best_formula || ""}
              expressionJson={latestGen?.best_expression_json}
              bestIc={latestGen?.best_ic || 0}
              complexity={latestGen?.best_complexity || 0}
              generation={latestGen?.generation || 0}
            />

            {/* Elite tracker */}
            <EliteTrackerPanel elites={store.gpEliteLineage} />

            {/* Lineage tree */}
            {store.gpEliteLineage.length > 0 && (
              <LineageTree elites={store.gpEliteLineage} />
            )}
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          LLM Extraction Tab
          ════════════════════════════════════════════════════════════ */}
      {activeTab === "llm" && (
        <div className="flex gap-4 flex-1">
          <div className="w-80 flex-shrink-0 border rounded-xl p-3 space-y-3">
            <h3 className="font-semibold text-sm">{t.fmExtractText || "Extract from Text"}</h3>
            <textarea
              value={llmText}
              onChange={(e) => setLlmText(e.target.value)}
              className="w-full h-40 rounded border bg-background px-2 py-1 text-sm resize-none"
              placeholder={t.fmPasteHint || "Paste research text containing factor formulas..."}
            />
            <button
              onClick={() => store.extractFromText(llmText)}
              disabled={store.llmLoading || !llmText.trim()}
              className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
            >
              {store.llmLoading ? t.fmExtracting || "Extracting..." : t.fmExtractBtn || "Extract Factors"}
            </button>

            <h3 className="font-semibold text-sm pt-4 border-t">{t.fmUploadPdf || "Upload PDF Paper"}</h3>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="text-sm"
            />
            <button
              onClick={() => selectedFile && store.extractFromPdf(selectedFile)}
              disabled={store.llmLoading || !selectedFile}
              className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
            >
              {t.fmUploadExtract || "Upload & Extract"}
            </button>
          </div>

          <div className="flex-1 border rounded-xl p-3">
            <h3 className="font-semibold text-sm mb-2">{t.fmExtractedCandidates || "Extracted Candidates"}</h3>
            <CandidatesTable
              candidates={store.candidates}
              loading={store.candidatesLoading}
              onValidate={handleValidation}
              onPromote={(id) => {
                const c = store.candidates.find((x) => x.id === id);
                store.promoteCandidate(id, "mined", "momentum", c?.name || "", "");
              }}
              onDelete={store.deleteCandidate}
            />
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          Hybrid Tab
          ════════════════════════════════════════════════════════════ */}
      {activeTab === "hybrid" && (
        <div className="flex gap-4 flex-1">
          <div className="w-72 border rounded-xl p-3 space-y-3">
            <h3 className="font-semibold text-sm">{t.fmHybridTitle || "Hybrid GP+LLM"}</h3>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">{t.fmMaxCycles || "Max Cycles"}</label>
              <input
                type="number"
                defaultValue={5}
                min={1}
                max={20}
                className="w-full rounded border bg-background px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={() => store.startHybridRun({ max_cycles: 5, gp_config: gpConfig })}
              disabled={store.hybridLoading}
              className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
            >
              {store.hybridLoading ? t.fmStarting || "Starting..." : t.fmStartHybrid || "Start Hybrid Mining"}
            </button>
          </div>
          <div className="flex-1 border rounded-xl p-3">
            <h3 className="text-sm font-semibold mb-2">{t.fmHybridTitle || "Hybrid"} Results</h3>
            {store.hybridStatus === "idle" && (
              <p className="text-xs text-muted-foreground">{t.fmHybridIdle || "Start a hybrid run to see results here."}</p>
            )}
            {store.hybridStatus === "running" && (
              <p className="text-xs text-muted-foreground">{t.fmHybridRunning || "Hybrid GP+LLM evolution in progress..."}</p>
            )}
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          Candidates Tab
          ════════════════════════════════════════════════════════════ */}
      {activeTab === "candidates" && (
        <div className="flex-1 border rounded-xl p-3 overflow-y-auto">
          <h3 className="font-semibold text-sm mb-2">
            {t.fmDiscoveredCandidates || "Discovered Candidates"} ({store.candidates.length})
          </h3>
          <CandidatesTable
            candidates={store.candidates}
            loading={store.candidatesLoading}
            onValidate={handleValidation}
            onPromote={(id) => {
              const c = store.candidates.find((x) => x.id === id);
              store.promoteCandidate(id, "mined", "momentum", c?.name || "", "");
            }}
            onDelete={store.deleteCandidate}
          />

          {/* Validation Result Modal */}
          {selectedCandidate && validationResult && (
            <div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
              onClick={() => setSelectedCandidate(null)}
            >
              <div
                className="bg-card border rounded-xl p-4 w-96 max-h-[80vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="font-bold text-sm mb-3">{t.fmValidationResults || "Validation Results"}</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span>{t.fmSyntaxValid || "Syntax"}:</span>
                    <span className={validationResult.syntax_valid ? "text-success" : "text-destructive"}>
                      {String(validationResult.syntax_valid)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>{t.fmLookaheadClean || "Lookahead Clean"}:</span>
                    <span className={validationResult.lookahead_clean ? "text-success" : "text-destructive"}>
                      {String(validationResult.lookahead_clean)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>{t.fmCoverage || "Coverage"}:</span>
                    <span>{(validationResult.coverage * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{t.fmNaN || "NaN Ratio"}:</span>
                    <span>{(validationResult.nan_ratio * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{t.fmInfCount || "Inf Count"}:</span>
                    <span>{validationResult.inf_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{t.fmMaxCorr || "Max Zoo Corr"}:</span>
                    <span>{validationResult.max_correlation_with_zoo?.toFixed(4)}</span>
                  </div>
                  {validationResult.ic_stability?.length > 0 && (
                    <div className="flex justify-between">
                      <span>{t.fmIcStability || "IC Stability"}:</span>
                      <span>{validationResult.ic_stability.map((v: number) => v.toFixed(4)).join(", ")}</span>
                    </div>
                  )}
                  {validationResult.warnings?.length > 0 && (
                    <div>
                      {validationResult.warnings.map((w: string, i: number) => (
                        <p key={i} className="text-warning">⚠ {w}</p>
                      ))}
                    </div>
                  )}
                  {validationResult.passed && (
                    <p className="text-success font-semibold pt-2">✓ {t.fmPassedChecks || "All checks passed"}</p>
                  )}
                </div>
                <button
                  onClick={() => setSelectedCandidate(null)}
                  className="w-full mt-3 px-3 py-1.5 bg-muted text-foreground rounded text-sm"
                >
                  {t.fmClose || "Close"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          History Tab
          ════════════════════════════════════════════════════════════ */}
      {activeTab === "history" && (
        <div className="flex-1 border rounded-xl p-3 overflow-y-auto">
          <h3 className="font-semibold text-sm mb-2">{t.fmMiningHistory || "Mining History"}</h3>
          {store.miningHistory.length === 0 && (
            <p className="text-xs text-muted-foreground">{t.fmNoRuns || "No runs yet"}</p>
          )}
          {store.miningHistory.map((run) => (
            <div key={run.id} className="border-b py-2 flex justify-between items-center text-sm">
              <div>
                <span className="font-medium">{run.type?.toUpperCase()}</span>
                <span className="text-muted-foreground ml-2">{run.id?.slice(0, 8)}...</span>
                {run.candidates_count != null && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    ({run.candidates_count} candidates)
                  </span>
                )}
              </div>
              <span
                className={cn(
                  "text-xs px-2 py-0.5 rounded",
                  run.status === "completed"
                    ? "bg-success/10 text-success"
                    : run.status === "failed"
                      ? "bg-destructive/10 text-destructive"
                      : "bg-muted text-muted-foreground"
                )}
              >
                {run.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          Compare Tab — Multi-run IC curve overlay
          ════════════════════════════════════════════════════════════ */}
      {activeTab === "compare" && (
        <div className="flex flex-col gap-3 flex-1 min-h-0 overflow-y-auto">
          <RunComparisonView
            runs={store.miningHistory.map((r) => ({
              ...r,
              generations: [], // generations not available in summary; loaded on demand
            }))}
          />
        </div>
      )}
    </div>
  );
}
