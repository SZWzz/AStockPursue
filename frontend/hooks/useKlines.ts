import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useKlines(symbol: string | null, freq = 'daily') {
  return useSWR(symbol ? `/api/market/bars?symbol=${symbol}&frequency=${freq}` : null, fetcher, { refreshInterval: 10000 })
}
