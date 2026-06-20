// frontend/stores/screenerStore.ts
import { create } from 'zustand'

interface ScreenerState {
  conditions: Record<string, any>
  sortField: string
  sortOrder: 'asc' | 'desc'
  setCondition: (key: string, value: any) => void
  setSort: (field: string, order: 'asc' | 'desc') => void
  reset: () => void
}

export const useScreenerStore = create<ScreenerState>()((set) => ({
  conditions: {},
  sortField: '',
  sortOrder: 'desc',
  setCondition: (key, value) => set(s => ({ conditions: { ...s.conditions, [key]: value } })),
  setSort: (field, order) => set({ sortField: field, sortOrder: order }),
  reset: () => set({ conditions: {}, sortField: '', sortOrder: 'desc' }),
}))
