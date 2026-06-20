import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useFactors(params?: { search?: string }) {
  const query = new URLSearchParams(params as Record<string,string> || {}).toString()
  return useSWR(`/api/factors${query ? '?' + query : ''}`, fetcher)
}
