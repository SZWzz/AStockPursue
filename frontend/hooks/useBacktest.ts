import useSWR from 'swr'
export function useBacktest(id: string | null) {
  return useSWR(id ? `/api/backtest/${id}` : null)
}
