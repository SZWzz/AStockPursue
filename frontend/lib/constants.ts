// frontend/lib/constants.ts
export const OLED = {
  background: '#020617',
  surface1: '#0A0F1D',
  surface2: '#0F172A',
  surface3: '#1A1E2F',
  borderSubtle: '#1E293B',
  borderDefault: '#272F42',
  borderStrong: '#334155',
  primary: '#FB923C',
  primaryHover: '#FBA86C',
  up: '#22C55E',
  down: '#EF4444',
  foreground: '#F8FAFC',
  foregroundSecondary: '#94A3B8',
  foregroundMuted: '#64748B',
} as const

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8899'
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8899/ws'
