import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '@/stores'

describe('useUIStore', () => {
  beforeEach(() =>
    useUIStore.setState({
      sidebarCollapsed: false,
      onboardingCompleted: false,
      onboardingDismissed: false,
    })
  )

  it('has default sidebarCollapsed = false', () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('toggles sidebar', () => {
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('has default onboardingCompleted = false', () => {
    expect(useUIStore.getState().onboardingCompleted).toBe(false)
  })

  it('has default onboardingDismissed = false', () => {
    expect(useUIStore.getState().onboardingDismissed).toBe(false)
  })

  it('sets onboardingCompleted to true', () => {
    useUIStore.getState().setOnboardingCompleted()
    expect(useUIStore.getState().onboardingCompleted).toBe(true)
  })

  it('sets onboardingDismissed to true', () => {
    useUIStore.getState().dismissOnboarding()
    expect(useUIStore.getState().onboardingDismissed).toBe(true)
  })
})
