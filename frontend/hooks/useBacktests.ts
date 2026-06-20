import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useBacktests() { return useSWR('/api/backtest', fetcher) }
