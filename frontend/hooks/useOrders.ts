import useSWR from 'swr'
const fetcher = (url: string) => fetch(url).then(r => r.json())
export function useOrders(params?: { status?: string }) {
  const query = new URLSearchParams(params as Record<string,string> || {}).toString()
  return useSWR(`/api/trading/orders${query ? '?' + query : ''}`, fetcher, { refreshInterval: 3000 })
}
