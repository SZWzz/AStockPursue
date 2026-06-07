import { create } from "zustand";
import { api } from "@/lib/api";

interface ScreenCondition {
  field: string;
  operator: string;
  value: number | [number, number];
}

interface Preset {
  id: number;
  name: string;
  conditions: ScreenCondition[];
  universe: string[];
  is_system: boolean;
}

interface ScreenerResult {
  symbol: string;
  name: string;
  _data_source?: string;
  _error?: string;
  [key: string]: unknown;
}

interface FieldDef {
  name: string;
  label: string;
  category: string;
  source: string;
}

interface ScreenerState {
  conditions: ScreenCondition[];
  universe: string[];
  results: ScreenerResult[];
  loading: boolean;
  presets: Preset[];
  presetsLoading: boolean;
  fields: FieldDef[];
  fieldsLoading: boolean;
  mode: "filter" | "rank" | "score";
  topN: number;
  dataSource: string;

  addCondition: () => void;
  removeCondition: (idx: number) => void;
  updateCondition: (idx: number, c: ScreenCondition) => void;
  runScreen: () => Promise<void>;
  loadPresets: () => Promise<void>;
  savePreset: (name: string) => Promise<void>;
  deletePreset: (id: number) => Promise<void>;
  aiRecommend: () => Promise<Preset[]>;
  batchAddWatchlist: (symbols: string[]) => Promise<void>;
  batchBacktest: (symbols: string[]) => Promise<void>;
  loadFields: () => Promise<void>;
  setMode: (mode: "filter" | "rank" | "score") => void;
  setTopN: (n: number) => void;
  setUniverse: (codes: string[]) => void;
  applyPreset: (preset: Preset) => void;
  applyAiRecommend: (combo: { factors?: string[]; conditions?: ScreenCondition[]; name?: string }) => void;
}

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  conditions: [{ field: "close", operator: ">", value: 0 }],
  universe: [],
  results: [],
  loading: false,
  presets: [],
  presetsLoading: false,
  fields: [],
  fieldsLoading: false,
  mode: "filter" as const,
  topN: 50,
  dataSource: "",

  addCondition: () => set((s) => ({ conditions: [...s.conditions, { field: "close", operator: ">", value: 0 }] })),
  removeCondition: (idx) => set((s) => ({ conditions: s.conditions.filter((_, i) => i !== idx) })),
  updateCondition: (idx, c) => set((s) => {
    const arr = [...s.conditions];
    arr[idx] = c;
    return { conditions: arr };
  }),

  setMode: (mode) => set({ mode }),
  setTopN: (n) => set({ topN: n }),
  setUniverse: (codes: string[]) => set({ universe: codes }),

  applyPreset: (preset: Preset) => {
    set({
      conditions: preset.conditions || [{ field: "close", operator: ">", value: 0 }],
      universe: preset.universe || [],
    });
  },

  applyAiRecommend: (combo: { factors?: string[]; conditions?: ScreenCondition[]; name?: string }) => {
    if (combo.factors && combo.factors.length > 0) {
      const conditions: ScreenCondition[] = combo.factors.map((f) => ({
        field: f,
        operator: ">",
        value: 0,
      }));
      set({ conditions: conditions.length > 0 ? conditions : [{ field: "close", operator: ">", value: 0 }] });
    }
    if (combo.conditions && combo.conditions.length > 0) {
      set({ conditions: combo.conditions });
    }
  },

  runScreen: async () => {
    set({ loading: true });
    try {
      const { conditions, universe, mode, topN } = get();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data: any = await api.runScreener({ conditions, universe, mode, top_n: topN });
      const results = data?.results || [];
      const ds = data?.data_source || (results.length > 0 && results[0]?._data_source) || "";
      // Show error message from backend if present
      const errorMsg = results.length === 1 && results[0]?._error ? results[0]._error : "";
      if (errorMsg) {
        console.warn("Screener error:", errorMsg);
      }
      set({ results, dataSource: ds, loading: false });
    } catch { set({ loading: false }); }
  },

  loadPresets: async () => {
    set({ presetsLoading: true });
    try {
      const data = await api.listScreenerPresets();
      set({ presets: Array.isArray(data) ? data : [], presetsLoading: false });
    } catch { set({ presetsLoading: false }); }
  },

  savePreset: async (name) => {
    const { conditions, universe } = get();
    await api.saveScreenerPreset({ name, conditions, universe });
    await get().loadPresets();
  },

  deletePreset: async (id) => {
    await api.deleteScreenerPreset(id);
    await get().loadPresets();
  },

  aiRecommend: async () => {
    const data = await api.aiRecommendScreener();
    return data || [];
  },

  batchAddWatchlist: async (symbols) => {
    await api.screenerBatch({ action: "add_watchlist", symbols });
  },

  batchBacktest: async (symbols) => {
    await api.screenerBatch({ action: "backtest_basket", symbols });
  },

  loadFields: async () => {
    set({ fieldsLoading: true });
    try {
      const data = await api.getScreenerFields();
      set({ fields: Array.isArray(data) ? data : [], fieldsLoading: false });
    } catch { set({ fieldsLoading: false }); }
  },
}));
