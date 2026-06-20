import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function usePositions() {
  return useSWR('/api/portfolio', fetcher, { refreshInterval: 5000 })
}
