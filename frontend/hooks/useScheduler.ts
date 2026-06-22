import useSWR from 'swr'
export function useScheduler() { return useSWR('/api/scheduler') }
