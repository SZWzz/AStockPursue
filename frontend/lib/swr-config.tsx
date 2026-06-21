'use client'
import { SWRConfig } from 'swr'

const fetcher = async (url: string) => {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export const swrConfig = {
  fetcher,
  dedupingInterval: 2000,
  errorRetryCount: 3,
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
}

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return <SWRConfig value={swrConfig}>{children}</SWRConfig>
}
