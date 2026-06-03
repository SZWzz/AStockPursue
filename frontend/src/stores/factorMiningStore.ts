import { create } from "zustand";
import { api } from "@/lib/api";
import type {
  GpConfig,
  GpProgress,
  GpResult,
  GenerationSnapshot,
  FactorCandidate,
  ValidationResult,
  MiningRunSummary,
  EliteEntry,
} from "@/types/api";

interface FactorMiningState {
  // GP
  gpJobId: string | null;
  gpStatus: string;
  gpProgress: GpProgress | null;
  gpGenerations: GenerationSnapshot[];
  gpResult: GpResult | null;
  gpLoading: boolean;
  gpDataSource: string;
  gpDataSourceDetail: string;
  gpEliteLineage: EliteEntry[];
  startGpRun: (config: GpConfig) => Promise<string>;
  cancelGpRun: () => Promise<void>;
  fetchGpGenerations: (jobId: string) => Promise<void>;
  fetchGpResult: (jobId: string) => Promise<void>;

  // LLM
  llmLoading: boolean;
  extractFromText: (text: string) => Promise<FactorCandidate[]>;
  extractFromPdf: (file: File) => Promise<FactorCandidate[]>;
  debateCandidates: (candidateIds: string[]) => Promise<void>;

  // Hybrid
  hybridJobId: string | null;
  hybridStatus: string;
  hybridLoading: boolean;
  startHybridRun: (config: any) => Promise<string>;

  // Candidates
  candidates: FactorCandidate[];
  candidatesLoading: boolean;
  fetchCandidates: () => Promise<void>;
  validateCandidate: (id: string) => Promise<ValidationResult>;
  promoteCandidate: (id: string, zoo: string, theme: string, name: string, desc: string) => Promise<void>;
  deleteCandidate: (id: string) => Promise<void>;

  // History
  miningHistory: MiningRunSummary[];
  fetchMiningHistory: () => Promise<void>;

  // SSE
  subscribeToJob: (jobId: string) => void;
  unsubscribeFromJob: () => void;
  sseSource: EventSource | null;
}

export const useFactorMiningStore = create<FactorMiningState>((set, get) => ({
  gpJobId: null,
  gpStatus: "idle",
  gpProgress: null,
  gpGenerations: [],
  gpResult: null,
  gpLoading: false,
  gpDataSource: "",
  gpDataSourceDetail: "",
  gpEliteLineage: [],

  startGpRun: async (config: GpConfig) => {
    set({ gpLoading: true, gpStatus: "starting", gpGenerations: [], gpResult: null, gpDataSource: "", gpDataSourceDetail: "", gpEliteLineage: [] });
    try {
      const data = await api.startGpRun(config);
      set({ gpJobId: data.job_id, gpStatus: "running", gpLoading: false });
      get().subscribeToJob(data.job_id);
      return data.job_id;
    } catch {
      set({ gpLoading: false, gpStatus: "error" });
      throw new Error("Failed to start GP run");
    }
  },

  cancelGpRun: async () => {
    const { gpJobId } = get();
    if (!gpJobId) return;
    try {
      await api.cancelGpRun(gpJobId);
      set({ gpStatus: "cancelled" });
      get().unsubscribeFromJob();
    } catch (e) {
      console.warn("[factorMining] Cancel GP run failed:", e);
    }
  },

  fetchGpGenerations: async (jobId: string) => {
    try {
      const data = await api.getGenerationHistory(jobId);
      set({ gpGenerations: data });
    } catch (e) {
      console.warn("[factorMining] Fetch GP generations failed:", e);
    }
  },

  fetchGpResult: async (jobId: string) => {
    try {
      const data = await api.getGpResult(jobId);
      set({ gpResult: data });
    } catch (e) {
      console.warn("[factorMining] Fetch GP result failed:", e);
    }
  },

  // LLM
  llmLoading: false,
  extractFromText: async (text: string) => {
    set({ llmLoading: true });
    try {
      const data = await api.llmExtractText(text);
      const candidates = data.candidates || [];
      return candidates;
    } catch {
      throw new Error("LLM extraction failed");
    } finally {
      set({ llmLoading: false });
    }
  },

  extractFromPdf: async (file: File) => {
    set({ llmLoading: true });
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await api.llmExtractPdf(formData);
      const candidates = data.candidates || [];
      return candidates;
    } catch {
      throw new Error("PDF extraction failed");
    } finally {
      set({ llmLoading: false });
    }
  },

  debateCandidates: async (candidateIds: string[]) => {
    set({ llmLoading: true });
    try {
      await api.llmDebate(candidateIds);
      await get().fetchCandidates();
    } catch {
      throw new Error("Debate failed");
    } finally {
      set({ llmLoading: false });
    }
  },

  // Hybrid
  hybridJobId: null,
  hybridStatus: "idle",
  hybridLoading: false,
  startHybridRun: async (config: any) => {
    set({ hybridLoading: true });
    try {
      const data = await api.hybridStart(config);
      set({ hybridJobId: data.job_id, hybridStatus: "running", hybridLoading: false });
      get().subscribeToJob(data.job_id);
      return data.job_id;
    } catch {
      set({ hybridLoading: false });
      throw new Error("Failed to start hybrid run");
    }
  },

  // Candidates
  candidates: [],
  candidatesLoading: false,
  fetchCandidates: async () => {
    set({ candidatesLoading: true });
    try {
      const data = await api.fetchCandidates();
      set({ candidates: data.candidates || [] });
    } catch {
      // ignore
    } finally {
      set({ candidatesLoading: false });
    }
  },

  validateCandidate: async (id: string) => {
    const result = await api.validateCandidate(id);
    return result;
  },

  promoteCandidate: async (id: string, zoo: string, theme: string, name: string, desc: string) => {
    try {
      await api.promoteCandidate(id, { zoo, theme, name, description: desc });
      await get().fetchCandidates();
    } catch (e) {
      console.warn("[factorMining] Promote candidate failed:", e);
      throw e;  // re-throw so the UI can show a toast
    }
  },

  deleteCandidate: async (id: string) => {
    await api.deleteCandidate(id);
    await get().fetchCandidates();
  },

  // History
  miningHistory: [],
  fetchMiningHistory: async () => {
    try {
      const data = await api.fetchMiningHistory();
      set({ miningHistory: data.runs || [] });
    } catch (e) {
      console.warn("[factorMining] Fetch mining history failed:", e);
    }
  },

  // SSE
  sseSource: null,
  subscribeToJob: (jobId: string) => {
    const { sseSource } = get();
    if (sseSource) {
      sseSource.close();
    }

    // Read JWT from sessionStorage at connection time; for long-running jobs
    // the server should accept a short-lived SSE token or the SSE endpoint
    // should be backed by an httpOnly cookie (set by the backend auth middleware).
    const jwt = sessionStorage.getItem("vt_token") || "";
    const url = `/v1/factor-mining/gp/${jobId}/stream?jwt=${encodeURIComponent(jwt)}`;
    const es = new EventSource(url);

    es.addEventListener("progress", (e) => {
      try {
        const data = JSON.parse(e.data);
        set((state) => ({
          gpProgress: {
            ...state.gpProgress,
            ...data,
          } as GpProgress,
        }));
      } catch {
        // ignore
      }
    });

    es.addEventListener("generation_complete", (e) => {
      try {
        const data = JSON.parse(e.data);
        set((state) => ({
          gpGenerations: [
            ...state.gpGenerations,
            {
              generation: data.generation,
              best_fitness: data.best_fitness,
              mean_fitness: data.mean_fitness,
              std_fitness: data.std_fitness || 0,
              best_ic: data.best_ic,
              diversity: data.diversity || 0,
              best_formula: data.best_formula || "",
              best_expression_json: data.best_expression_json || undefined,
              best_complexity: data.best_complexity || 0,
              gen_seconds: data.gen_seconds || 0,
              fitness_distribution: data.fitness_distribution || undefined,
              elite_lineage: data.elite_lineage || undefined,
              data_source: data.data_source || "",
            },
          ],
          gpEliteLineage: data.elite_lineage || state.gpEliteLineage,
        }));
      } catch {
        // ignore
      }
    });

    es.addEventListener("data_source", (e) => {
      try {
        const data = JSON.parse(e.data);
        set({
          gpDataSource: data.source || "",
          gpDataSourceDetail: data.detail || "",
        });
      } catch {
        // ignore
      }
    });

    es.addEventListener("done", (e) => {
      try {
        const data = JSON.parse(e.data);
        set({ gpStatus: data.status || "completed" });
        es.close();
        // Fetch final result
        get().fetchGpResult(jobId);
        get().fetchCandidates();
      } catch {
        // ignore
      }
    });

    es.addEventListener("error", () => {
      // Browser will auto-reconnect; log the error for diagnostics.
      // Long-running GP jobs may fail if the JWT expires mid-stream —
      // use unsubscribeFromJob / subscribeToJob to manually reconnect.
      console.warn("[factorMining] GP SSE error — connection may be lost");
    });

    set({ sseSource: es });
  },

  unsubscribeFromJob: () => {
    const { sseSource } = get();
    if (sseSource) {
      sseSource.close();
      set({ sseSource: null });
    }
  },
}));
