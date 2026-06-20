import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useSystemStatus() {
  return useSWR('/api/system/status', fetcher, { refreshInterval: 30000 })
}
