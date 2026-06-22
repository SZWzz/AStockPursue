import useSWR from 'swr'
export function useFactors(params?: { search?: string }) {
  const query = new URLSearchParams(params as Record<string,string> || {}).toString()
  return useSWR(`/api/factors${query ? '?' + query : ''}`)
}
