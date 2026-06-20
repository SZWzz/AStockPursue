import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function usePaperAccounts() { return useSWR('/api/papertrading', fetcher) }
