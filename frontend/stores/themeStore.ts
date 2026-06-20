// frontend/stores/themeStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type LayoutPreset = 'compact' | 'standard'

interface ThemeState {
  layoutPreset: LayoutPreset
  fontSize: number // 12-16
  setLayoutPreset: (p: LayoutPreset) => void
  setFontSize: (n: number) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      layoutPreset: 'compact',
      fontSize: 13,
      setLayoutPreset: (p) => set({ layoutPreset: p }),
      setFontSize: (n) => set({ fontSize: Math.min(16, Math.max(12, n)) }),
    }),
    { name: 'theme-store' }
  )
)
