// frontend/stores/screenerStore.ts
import { create } from 'zustand'

export type ScreenMode = 'filter' | 'rank' | 'score'

interface ScreenerState {
  mode: ScreenMode
  conditions: Array<{ field: string; operator: string; value: string }>
  sortField: string
  sortDir: 'asc' | 'desc'
  presets: Array<{ name: string; config: Record<string, any> }>
  setMode: (mode: ScreenMode) => void
  addCondition: () => void
  updateCondition: (index: number, field: Partial<{ field: string; operator: string; value: string }>) => void
  removeCondition: (index: number) => void
  setSort: (field: string, dir: 'asc' | 'desc') => void
  savePreset: (name: string) => void
  loadPreset: (name: string) => void
}

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  mode: 'filter',
  conditions: [],
  sortField: 'change',
  sortDir: 'desc',
  presets: [],
  setMode: (mode) => set({ mode }),
  addCondition: () => set({ conditions: [...get().conditions, { field: 'price', operator: '>', value: '0' }] }),
  updateCondition: (index, field) => {
    const conditions = [...get().conditions]
    conditions[index] = { ...conditions[index], ...field }
    set({ conditions })
  },
  removeCondition: (index) => set({ conditions: get().conditions.filter((_, i) => i !== index) }),
  setSort: (field, dir) => set({ sortField: field, sortDir: dir }),
  savePreset: (name) => set({ presets: [...get().presets, { name, config: JSON.parse(JSON.stringify(get())) }] }),
  loadPreset: (name) => {
    const preset = get().presets.find((p) => p.name === name)
    if (preset) {
      const { presets, ...config } = preset.config
      set({ ...config, presets: get().presets })
    }
  },
}))
