import useSWR from 'swr'

export interface UserSettings {
  language?: string
  theme?: string
  default_market?: string
  default_freq?: string
  default_symbols?: string[]
  notifications_enabled?: boolean
  general?: {
    language?: string
    theme?: string
    default_market?: string
    default_freq?: string
    default_symbols?: string[]
  }
}

export function useSettings() {
  return useSWR<UserSettings>('/api/settings')
}
