import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useBacktest(id: string | null) {
  return useSWR(id ? `/api/backtest/${id}` : null, fetcher)
}
