import useSWR from 'swr'
export function useBacktests() { return useSWR('/api/backtest') }
