import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useMarketData(symbol: string | null) {
  return useSWR(symbol ? `/api/market/bars?symbol=${symbol}` : null, fetcher, { refreshInterval: 5000 })
}
