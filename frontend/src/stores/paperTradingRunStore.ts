import { create } from "zustand";
import {
  paperTradingApi,
  type RunDetail,
  type RunSummary,
} from "@/services/paperTrading";

interface PaperTradingRunState {
  runs: RunSummary[];
  runsLoading: boolean;
  activeRunId: string | null;
  activeRunDetail: RunDetail | null;
  detailLoading: boolean;

  fetchRuns: () => Promise<void>;
  selectRun: (runId: string) => Promise<void>;
  createRun: (req: Parameters<typeof paperTradingApi.createRun>[0]) => Promise<string>;
  startRun: (runId: string) => Promise<void>;
  stopRun: (runId: string) => Promise<void>;
  pauseRun: (runId: string) => Promise<void>;
  resumeRun: (runId: string) => Promise<void>;
  deleteRun: (runId: string) => Promise<void>;
  reset: () => void;
}

const initialState = {
  runs: [],
  runsLoading: false,
  activeRunId: null,
  activeRunDetail: null,
  detailLoading: false,
};

export const usePaperTradingRunStore = create<PaperTradingRunState>((set, get) => ({
  ...initialState,

  fetchRuns: async () => {
    set({ runsLoading: true });
    try {
      const runs = await paperTradingApi.listRuns();
      set({ runs, runsLoading: false });
    } catch {
      set({ runsLoading: false });
    }
  },

  selectRun: async (runId: string) => {
    set({ activeRunId: runId, detailLoading: true });
    try {
      const detail = await paperTradingApi.getRun(runId);
      set({ activeRunDetail: detail, detailLoading: false });
    } catch {
      set({ detailLoading: false });
    }
  },

  createRun: async (req) => {
    const result = await paperTradingApi.createRun(req);
    await get().fetchRuns();
    return result.id;
  },

  startRun: async (runId: string) => {
    await paperTradingApi.startRun(runId);
    await get().fetchRuns();
  },

  stopRun: async (runId: string) => {
    await paperTradingApi.stopRun(runId);
    await get().fetchRuns();
    if (get().activeRunId === runId) {
      await get().selectRun(runId);
    }
  },

  pauseRun: async (runId: string) => {
    await paperTradingApi.pauseRun(runId);
    await get().fetchRuns();
  },

  resumeRun: async (runId: string) => {
    await paperTradingApi.resumeRun(runId);
    await get().fetchRuns();
  },

  deleteRun: async (runId: string) => {
    await paperTradingApi.deleteRun(runId);
    if (get().activeRunId === runId) {
      set({ activeRunId: null, activeRunDetail: null });
    }
    await get().fetchRuns();
  },

  reset: () => {
    set(initialState);
  },
}));
