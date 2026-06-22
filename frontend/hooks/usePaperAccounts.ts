import useSWR from 'swr'
export function usePaperAccounts() { return useSWR('/api/papertrading') }
