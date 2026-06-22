import useSWR from 'swr'
export function useSystemStatus() {
  return useSWR('/api/system/status', { refreshInterval: 30000 })
}
