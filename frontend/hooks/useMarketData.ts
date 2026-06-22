import useSWR from 'swr'
export function useMarketData(symbol: string | null) {
  return useSWR(symbol ? `/api/market/bars?symbol=${symbol}` : null, { refreshInterval: 5000 })
}
