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
      const r = await api.attributionBrinson({ run_id: id }) as Record<string, unknown> | null;
      set({ brinsonResult: r });
    } catch (e) { console.warn("[attribution] Brinson compute failed:", e); }
    set({ loading: false });
  },
  computeFactor: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await api.attributionFactor({ run_id: id, factors: [] }) as Record<string, unknown> | null;
      set({ factorResult: r });
    } catch (e) { console.warn("[attribution] Factor attr compute failed:", e); }
    set({ loading: false });
  },
  computeSector: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await api.attributionSector({ run_id: id, classification: "sw" }) as Record<string, unknown> | null;
      set({ sectorResult: r });
    } catch (e) { console.warn("[attribution] Sector compute failed:", e); }
    set({ loading: false });
  },
  computeDecomp: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await api.attributionDecomp({ run_id: id }) as Record<string, unknown> | null;
      set({ decompResult: r });
    } catch (e) { console.warn("[attribution] Decomp compute failed:", e); }
    set({ loading: false });
  },
  computeFull: async () => {
    const id = get().selectedRunId;
    if (!id) return;
    set({ loading: true });
    try {
      const r = await api.attributionFull({ run_id: id }) as Record<string, unknown> | null;
      // Only overwrite fields that are present in the response — preserve
      // individually-computed results that the full report may omit.
      const patch: Partial<AttributionState> = { fullReport: r, loading: false };
      if ((r as any)?.brinson) patch.brinsonResult = (r as any).brinson;
      if ((r as any)?.factor) patch.factorResult = (r as any).factor;
      if ((r as any)?.sector) patch.sectorResult = (r as any).sector;
      if ((r as any)?.time_series) patch.decompResult = (r as any).time_series;
      set(patch);
      return;
    } catch (e) { console.warn("[attribution] Full report compute failed:", e); }
    set({ loading: false });
  },
}));
