import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '@/stores'

describe('useUIStore', () => {
  beforeEach(() => useUIStore.setState({ sidebarCollapsed: false }))

  it('has default sidebarCollapsed = false', () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('toggles sidebar', () => {
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })
})
