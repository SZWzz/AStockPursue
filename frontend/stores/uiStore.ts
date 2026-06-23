// frontend/stores/uiStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  onboardingCompleted: boolean
  onboardingDismissed: boolean
  setOnboardingCompleted: () => void
  dismissOnboarding: () => void
  resetOnboarding: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set(s => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      onboardingCompleted: false,
      onboardingDismissed: false,
      setOnboardingCompleted: () => set({ onboardingCompleted: true }),
      dismissOnboarding: () => set({ onboardingDismissed: true }),
      resetOnboarding: () => set({ onboardingCompleted: false, onboardingDismissed: false }),
    }),
    { name: 'ui-store', version: 2, migrate: (persisted) => persisted as UIState }
  )
)
