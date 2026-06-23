import useSWR from 'swr'
import type { Portfolio } from '@/types'

export function usePositions() {
  return useSWR<Portfolio>('/api/portfolio', { refreshInterval: 5000 })
}
