import useSWR from 'swr'
export function useKlines(symbol: string | null, freq = 'daily') {
  return useSWR(symbol ? `/api/market/bars?symbol=${symbol}&frequency=${freq}` : null, { refreshInterval: 10000 })
}
