import { create } from "zustand";
import { api } from "@/lib/api";

interface AttributionState {
  selectedRunId: string | null;
  brinsonResult: Record<string, unknown> | null;
  factorResult: Record<string, unknown> | null;
  sectorResult: Record<string, unknown> | null;
  decompResult: Record<string, unknown> | null;
  fullReport: Record<string, unknown> | null;
  loading: boolean;

  setRunId: (id: string) => void;
  computeBrinson: () => Promise<void>;
  computeFactor: () => Promise<void>;
  computeSector: () => Promise<void>;
  computeDecomp: () => Promise<void>;
  computeFull: () => Promise<void>;
}

export const useAttributionStore = create<AttributionState>((set, get) => ({
  selectedRunId: null,
  brinsonResult: null,
  factorResult: null,
  sectorResult: null,
  decompResult: null,
  fullReport: null,
  loading: false,

  setRunId: (id) => set({ selectedRunId: id }),

  computeBrinson: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await (api as any).attributionBrinson({ run_id: id });
      set({ brinsonResult: r });
    } catch { /* ignore */ }
    set({ loading: false });
  },
  computeFactor: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await (api as any).attributionFactor({ run_id: id, factors: [] });
      set({ factorResult: r });
    } catch { /* ignore */ }
    set({ loading: false });
  },
  computeSector: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await (api as any).attributionSector({ run_id: id, classification: "sw" });
      set({ sectorResult: r });
    } catch { /* ignore */ }
    set({ loading: false });
  },
  computeDecomp: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await (api as any).attributionDecomp({ run_id: id });
      set({ decompResult: r });
    } catch { /* ignore */ }
    set({ loading: false });
  },
  computeFull: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await (api as any).attributionFull({ run_id: id });
      set({ fullReport: r, brinsonResult: (r as any)?.brinson, factorResult: (r as any)?.factor, sectorResult: (r as any)?.sector, decompResult: (r as any)?.time_series });
    } catch { /* ignore */ }
    set({ loading: false });
  },
}));
