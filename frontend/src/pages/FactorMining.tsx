import { useState, useEffect, useCallback } from "react";
import { useI18n } from "@/lib/i18n";
import { useFactorMiningStore } from "@/stores/factorMiningStore";
import { EvolutionChart } from "@/components/factor-mining/EvolutionChart";
import { ExpressionTreeViewer } from "@/components/factor-mining/ExpressionTreeViewer";
import { CandidatesTable } from "@/components/factor-mining/CandidatesTable";
import { MiningProgressCard } from "@/components/factor-mining/MiningProgressCard";
import { cn } from "@/lib/utils";

type TabKey = "gp" | "llm" | "hybrid" | "candidates" | "history";

export function FactorMining() {
  const { t } = useI18n();
  const store = useFactorMiningStore();
  const [activeTab, setActiveTab] = useState<TabKey>("gp");

  // GP config state
  const [gpConfig, setGpConfig] = useState({
    population_size: 100,
    generations: 30,
    tournament_size: 7,
    crossover_prob: 0.7,
    mutation_prob: 0.2,
    fitness_metric: "ic_mean" as const,
    complexity_penalty: "bic" as const,
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

  // Promote modal

  useEffect(() => {
    store.fetchCandidates();
    store.fetchMiningHistory();
    return () => {
      store.unsubscribeFromJob();
    };
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
    { key: "gp", label: "GP Evolution" },
    { key: "llm", label: "LLM Extraction" },
    { key: "hybrid", label: "Hybrid Search" },
    { key: "candidates", label: "Candidates" },
    { key: "history", label: "History" },
  ];

  return (
    <div className="flex flex-col h-full p-4 gap-4">
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

      {/* GP Evolution Tab */}
      {activeTab === "gp" && (
        <div className="flex gap-4 flex-1 overflow-hidden">
          {/* Config panel */}
          <div className="w-72 flex-shrink-0 border rounded-xl p-3 overflow-y-auto space-y-3">
            <h3 className="font-semibold text-sm">GP Setup</h3>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Population Size</label>
              <input type="number" value={gpConfig.population_size} onChange={(e) => setGpConfig({ ...gpConfig, population_size: +e.target.value })}
                className="w-full rounded border bg-background px-2 py-1 text-sm" min={10} max={500} />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Generations</label>
              <input type="number" value={gpConfig.generations} onChange={(e) => setGpConfig({ ...gpConfig, generations: +e.target.value })}
                className="w-full rounded border bg-background px-2 py-1 text-sm" min={5} max={200} />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Train Start</label>
              <input type="text" value={gpConfig.train_start} onChange={(e) => setGpConfig({ ...gpConfig, train_start: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1 text-sm" />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Train End</label>
              <input type="text" value={gpConfig.train_end} onChange={(e) => setGpConfig({ ...gpConfig, train_end: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1 text-sm" />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Test Start</label>
              <input type="text" value={gpConfig.test_start} onChange={(e) => setGpConfig({ ...gpConfig, test_start: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1 text-sm" />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Test End</label>
              <input type="text" value={gpConfig.test_end} onChange={(e) => setGpConfig({ ...gpConfig, test_end: e.target.value })}
                className="w-full rounded border bg-background px-2 py-1 text-sm" />
            </div>

            <button
              onClick={handleStartGp}
              disabled={store.gpStatus === "running"}
              className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm font-medium disabled:opacity-50"
            >
              {store.gpStatus === "running" ? "Running..." : store.gpStatus === "starting" ? "Starting..." : "Start Evolution"}
            </button>

            {store.gpStatus === "running" && (
              <button onClick={store.cancelGpRun} className="w-full px-3 py-1 bg-destructive/10 text-destructive rounded text-sm">
                Stop
              </button>
            )}
          </div>

          {/* Main area */}
          <div className="flex-1 flex flex-col gap-3 overflow-y-auto">
            <MiningProgressCard
              status={store.gpStatus}
              currentGeneration={store.gpGenerations.length}
              totalGenerations={gpConfig.generations}
              bestIC={store.gpGenerations.length > 0 ? store.gpGenerations[store.gpGenerations.length - 1].best_ic : 0}
            />
            <EvolutionChart generations={store.gpGenerations} />

            {store.gpResult && store.gpResult.result?.best_individuals?.[0] && (
              <div className="border rounded-xl p-3">
                <h3 className="text-sm font-semibold mb-2">Best Factor</h3>
                <p className="text-xs font-mono bg-muted p-2 rounded">{store.gpResult.result.best_individuals[0].formula}</p>
                {store.gpResult.result.best_individuals[0].expression_json && (
                  <ExpressionTreeViewer tree={store.gpResult.result.best_individuals[0].expression_json} />
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* LLM Extraction Tab */}
      {activeTab === "llm" && (
        <div className="flex gap-4 flex-1">
          <div className="w-80 flex-shrink-0 border rounded-xl p-3 space-y-3">
            <h3 className="font-semibold text-sm">Extract from Text</h3>
            <textarea
              value={llmText}
              onChange={(e) => setLlmText(e.target.value)}
              className="w-full h-40 rounded border bg-background px-2 py-1 text-sm resize-none"
              placeholder="Paste research text here..."
            />
            <button
              onClick={() => store.extractFromText(llmText)}
              disabled={store.llmLoading || !llmText.trim()}
              className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
            >
              {store.llmLoading ? "Extracting..." : "Extract Factors"}
            </button>

            <h3 className="font-semibold text-sm pt-4 border-t">Upload PDF</h3>
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
              Upload & Extract
            </button>
          </div>

          <div className="flex-1 border rounded-xl p-3">
            <h3 className="font-semibold text-sm mb-2">Extracted Candidates</h3>
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

      {/* Hybrid Tab */}
      {activeTab === "hybrid" && (
        <div className="flex gap-4 flex-1">
          <div className="w-72 border rounded-xl p-3 space-y-3">
            <h3 className="font-semibold text-sm">Hybrid GP + LLM</h3>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Max Cycles</label>
              <input type="number" defaultValue={5} min={1} max={20}
                className="w-full rounded border bg-background px-2 py-1 text-sm" />
            </div>
            <button
              onClick={() => store.startHybridRun({ max_cycles: 5, gp_config: gpConfig })}
              disabled={store.hybridLoading}
              className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
            >
              {store.hybridLoading ? "Starting..." : "Start Hybrid Run"}
            </button>
          </div>
          <div className="flex-1 border rounded-xl p-3">
            <h3 className="text-sm font-semibold mb-2">Hybrid Results</h3>
            {store.hybridStatus === "idle" && <p className="text-xs text-muted-foreground">Start a hybrid run to see results.</p>}
            {store.hybridStatus === "running" && <p className="text-xs text-muted-foreground">Running hybrid optimization...</p>}
          </div>
        </div>
      )}

      {/* Candidates Tab */}
      {activeTab === "candidates" && (
        <div className="flex-1 border rounded-xl p-3 overflow-y-auto">
          <h3 className="font-semibold text-sm mb-2">
            Discovered Factor Candidates ({store.candidates.length})
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
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedCandidate(null)}>
              <div className="bg-card border rounded-xl p-4 w-96 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                <h3 className="font-bold text-sm mb-3">Validation Results</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between"><span>Syntax Valid:</span><span className={validationResult.syntax_valid ? "text-success" : "text-destructive"}>{String(validationResult.syntax_valid)}</span></div>
                  <div className="flex justify-between"><span>Lookahead Clean:</span><span className={validationResult.lookahead_clean ? "text-success" : "text-destructive"}>{String(validationResult.lookahead_clean)}</span></div>
                  <div className="flex justify-between"><span>Coverage:</span><span>{(validationResult.coverage * 100).toFixed(1)}%</span></div>
                  <div className="flex justify-between"><span>NaN Ratio:</span><span>{(validationResult.nan_ratio * 100).toFixed(1)}%</span></div>
                  <div className="flex justify-between"><span>Inf Count:</span><span>{validationResult.inf_count}</span></div>
                  <div className="flex justify-between"><span>Max Correlation w/ Zoo:</span><span>{validationResult.max_correlation_with_zoo?.toFixed(4)}</span></div>
                  {validationResult.ic_stability?.length > 0 && (
                    <div className="flex justify-between"><span>IC Stability (per fold):</span><span>{validationResult.ic_stability.map((v: number) => v.toFixed(4)).join(", ")}</span></div>
                  )}
                  {validationResult.warnings?.length > 0 && (
                    <div>{validationResult.warnings.map((w: string, i: number) => <p key={i} className="text-warning">⚠ {w}</p>)}</div>
                  )}
                  {validationResult.passed && (
                    <p className="text-success font-semibold pt-2">✓ All checks passed — ready for promotion!</p>
                  )}
                </div>
                <button onClick={() => setSelectedCandidate(null)} className="w-full mt-3 px-3 py-1.5 bg-muted text-foreground rounded text-sm">Close</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === "history" && (
        <div className="flex-1 border rounded-xl p-3 overflow-y-auto">
          <h3 className="font-semibold text-sm mb-2">Mining Run History</h3>
          {store.miningHistory.length === 0 && <p className="text-xs text-muted-foreground">No mining runs yet.</p>}
          {store.miningHistory.map((run) => (
            <div key={run.id} className="border-b py-2 flex justify-between items-center text-sm">
              <div>
                <span className="font-medium">{run.type?.toUpperCase()}</span>
                <span className="text-muted-foreground ml-2">{run.id?.slice(0, 8)}...</span>
                {run.candidates_count != null && <span className="ml-2 text-xs text-muted-foreground">({run.candidates_count} candidates)</span>}
              </div>
              <span className={cn("text-xs px-2 py-0.5 rounded", run.status === "completed" ? "bg-success/10 text-success" : run.status === "failed" ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground")}>
                {run.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
