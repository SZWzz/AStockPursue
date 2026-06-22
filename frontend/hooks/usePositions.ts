import useSWR from 'swr'
export function usePositions() {
  return useSWR('/api/portfolio', { refreshInterval: 5000 })
}
