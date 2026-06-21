// frontend/stores/screenerStore.ts
import { create } from 'zustand'

export type ScreenMode = 'filter' | 'rank' | 'score'
export type LogicOp = 'AND' | 'OR'

interface ScreenerState {
  mode: ScreenMode
  conditions: Array<{ field: string; operator: string; value: string; logic?: LogicOp }>
  sortField: string
  sortDir: 'asc' | 'desc'
  presets: Array<{ name: string; config: Record<string, any> }>
  setMode: (mode: ScreenMode) => void
  addCondition: () => void
  updateCondition: (index: number, field: Partial<{ field: string; operator: string; value: string; logic: LogicOp }>) => void
  removeCondition: (index: number) => void
  toggleLogic: (index: number) => void
  clearConditions: () => void
  setSort: (field: string, dir: 'asc' | 'desc') => void
  savePreset: (name: string) => void
  loadPreset: (name: string) => void
  loadLocalPresets: () => void
}

const STORAGE_KEY = 'screener-presets'

function loadLocalPresets(): Array<{ name: string; config: Record<string, any> }> {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveLocalPresets(presets: Array<{ name: string; config: Record<string, any> }>) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets))
  } catch { /* ignore */ }
}

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  mode: 'filter',
  conditions: [],
  sortField: 'change',
  sortDir: 'desc',
  presets: [],
  setMode: (mode) => set({ mode }),
  addCondition: () =>
    set({
      conditions: [
        ...get().conditions,
        { field: 'price', operator: '>', value: '0', logic: 'AND' as LogicOp },
      ],
    }),
  updateCondition: (index, field) => {
    const conditions = [...get().conditions]
    conditions[index] = { ...conditions[index], ...field }
    set({ conditions })
  },
  removeCondition: (index) => set({ conditions: get().conditions.filter((_, i) => i !== index) }),
  toggleLogic: (index) => {
    const conditions = [...get().conditions]
    if (index > 0 && index < conditions.length) {
      conditions[index].logic = conditions[index].logic === 'OR' ? 'AND' : 'OR'
      set({ conditions })
    }
  },
  clearConditions: () => set({ conditions: [] }),
  setSort: (field, dir) => set({ sortField: field, sortDir: dir }),
  savePreset: (name) => {
    const updated = [...get().presets, { name, config: JSON.parse(JSON.stringify(get())) }]
    saveLocalPresets(updated)
    set({ presets: updated })
  },
  loadPreset: (name) => {
    const preset = get().presets.find((p) => p.name === name)
    if (preset) {
      const { presets, ...config } = preset.config
      set({ ...config, presets: get().presets })
    }
  },
  loadLocalPresets: () => {
    const local = loadLocalPresets()
    if (local.length > 0 && get().presets.length === 0) {
      set({ presets: local })
    }
  },
}))
