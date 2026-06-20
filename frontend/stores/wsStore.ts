// frontend/stores/wsStore.ts
import { create } from 'zustand'

interface WSState {
  connected: boolean
  lastHeartbeat: number
  subscriptions: Map<string, Set<string>>
  setConnected: (c: boolean) => void
  setHeartbeat: (t: number) => void
  addSubscription: (channel: string, symbols: string[]) => void
  removeSubscription: (channel: string, symbols: string[]) => void
  clearSubscriptions: () => void
}

export const useWSStore = create<WSState>()((set) => ({
  connected: false,
  lastHeartbeat: 0,
  subscriptions: new Map(),
  setConnected: (c) => set({ connected: c }),
  setHeartbeat: (t) => set({ lastHeartbeat: t }),
  addSubscription: (channel, symbols) => set(s => {
    const next = new Map(s.subscriptions)
    const existing = next.get(channel) || new Set()
    symbols.forEach(sym => existing.add(sym))
    next.set(channel, existing)
    return { subscriptions: next }
  }),
  removeSubscription: (channel, symbols) => set(s => {
    const next = new Map(s.subscriptions)
    const existing = next.get(channel)
    if (existing) {
      symbols.forEach(sym => existing.delete(sym))
      if (existing.size === 0) next.delete(channel)
      else next.set(channel, existing)
    }
    return { subscriptions: next }
  }),
  clearSubscriptions: () => set({ subscriptions: new Map() }),
}))
