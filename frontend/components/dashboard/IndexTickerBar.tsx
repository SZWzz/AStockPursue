// frontend/components/dashboard/IndexTickerBar.tsx
'use client'

import { useEffect, useState } from 'react'
import { wsClient } from '@/lib/ws'
import { cn } from '@/lib/utils'

interface TickerData {
  symbol: string
  price: number
  change: number
}

export function IndexTickerBar() {
  const [tickers, setTickers] = useState<Record<string, TickerData>>({
    '000001.SZ': { symbol: '000001.SZ', price: 0, change: 0 },
    '600519.SH': { symbol: '600519.SH', price: 0, change: 0 },
    '000300.SH': { symbol: '000300.SH', price: 0, change: 0 },
  })

  useEffect(() => {
    const unsub = wsClient.on('ticker', (_channel, data) => {
      if (data?.symbol && tickers[data.symbol]) {
        setTickers((prev) => ({
          ...prev,
          [data.symbol]: { symbol: data.symbol, price: data.price, change: data.change },
        }))
      }
    })
    return unsub
  }, [])

  return (
    <div className="flex gap-4 bg-white border border-[var(--border)] rounded-[6px] px-4 py-2">
      {Object.values(tickers).map((t) => (
        <div key={t.symbol} className="flex items-center gap-3">
          <span className="text-[12px] font-mono text-[var(--foreground)]">{t.symbol}</span>
          <span className="text-[14px] font-mono tabular-nums text-[var(--foreground)]">
            {t.price ? t.price.toFixed(2) : '--'}
          </span>
          <span className={cn(
            'text-[12px] font-mono',
            t.change > 0 ? 'text-[var(--up)]' : t.change < 0 ? 'text-[var(--down)]' : 'text-[var(--foreground-muted)]'
          )}>
            {t.change ? `${t.change > 0 ? '+' : ''}${(t.change * 100).toFixed(2)}%` : '--'}
          </span>
        </div>
      ))}
    </div>
  )
}
