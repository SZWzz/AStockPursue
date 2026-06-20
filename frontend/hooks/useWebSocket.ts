// frontend/hooks/useWebSocket.ts
'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { wsClient } from '@/lib/ws'
import { useAuth } from '@/lib/auth-client'

const ROUTE_CHANNELS: Record<string, { channel: string; symbols?: string[] }[]> = {
  '/': [{ channel: 'positions' }, { channel: 'ticker' }, { channel: 'system' }],
  '/trading': [{ channel: 'ticker' }, { channel: 'orders' }, { channel: 'positions' }],
  '/trading/orders': [{ channel: 'orders' }],
  '/trading/positions': [{ channel: 'positions' }],
  '/system': [{ channel: 'system' }],
}

export function useWebSocket() {
  const pathname = usePathname()
  const { token, isAuthenticated } = useAuth()

  useEffect(() => {
    if (!isAuthenticated || !token) return
    wsClient.connect(token)
    const channels = ROUTE_CHANNELS[pathname] || []
    channels.forEach(({ channel, symbols }) => wsClient.subscribe(channel, symbols || []))
    return () => {
      channels.forEach(({ channel, symbols }) => wsClient.unsubscribe(channel, symbols || []))
    }
  }, [pathname, isAuthenticated, token])
}
