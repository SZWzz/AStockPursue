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
  [key: string]: unknown;
}

interface ScreenerState {
  conditions: ScreenCondition[];
  universe: string[];
  results: ScreenerResult[];
  loading: boolean;
  presets: Preset[];
  presetsLoading: boolean;

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
}

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  conditions: [{ field: "close", operator: ">", value: 0 }],
  universe: [],
  results: [],
  loading: false,
  presets: [],
  presetsLoading: false,

  addCondition: () => set((s) => ({ conditions: [...s.conditions, { field: "close", operator: ">", value: 0 }] })),
  removeCondition: (idx) => set((s) => ({ conditions: s.conditions.filter((_, i) => i !== idx) })),
  updateCondition: (idx, c) => set((s) => {
    const arr = [...s.conditions];
    arr[idx] = c;
    return { conditions: arr };
  }),

  runScreen: async () => {
    set({ loading: true });
    try {
      const { conditions, universe } = get();
      const data = await (api as any).runScreener({ conditions, universe });
      set({ results: data?.results || [], loading: false });
    } catch { set({ loading: false }); }
  },

  loadPresets: async () => {
    set({ presetsLoading: true });
    try {
      const data = await (api as any).listScreenerPresets();
      set({ presets: Array.isArray(data) ? data : [], presetsLoading: false });
    } catch { set({ presetsLoading: false }); }
  },

  savePreset: async (name) => {
    const { conditions, universe } = get();
    await (api as any).saveScreenerPreset({ name, conditions, universe });
    await get().loadPresets();
  },

  deletePreset: async (id) => {
    await (api as any).deleteScreenerPreset(id);
    await get().loadPresets();
  },

  aiRecommend: async () => {
    const data = await (api as any).aiRecommendScreener();
    return data || [];
  },

  batchAddWatchlist: async (symbols) => {
    await (api as any).screenerBatch({ action: "add_watchlist", symbols });
  },

  batchBacktest: async (symbols) => {
    await (api as any).screenerBatch({ action: "backtest_basket", symbols });
  },
}));
