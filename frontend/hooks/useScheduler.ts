import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useScheduler() { return useSWR('/api/scheduler', fetcher) }
