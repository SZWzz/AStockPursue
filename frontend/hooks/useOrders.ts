import useSWR from 'swr'
export function useOrders(params?: { status?: string }) {
  const query = new URLSearchParams(params as Record<string,string> || {}).toString()
  return useSWR(`/api/trading/orders${query ? '?' + query : ''}`, { refreshInterval: 3000 })
}
