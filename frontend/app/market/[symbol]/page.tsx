// frontend/app/market/[symbol]/page.tsx — Symbol detail
'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CandlestickChart } from '@/components/financial/CandlestickChart'
import { OrderBook } from '@/components/financial/OrderBook'
import { Card } from '@/components/ui/card'
import { useKlines } from '@/hooks'
import { cn, formatPrice, formatPercent } from '@/lib/utils'

interface Level {
  price: number
  quantity: number
}

type Frequency = '1m' | '5m' | 'daily' | 'weekly'

const FREQUENCIES: { key: Frequency; label: string }[] = [
  { key: '1m', label: '1m' },
  { key: '5m', label: '5m' },
  { key: 'daily', label: 'D' },
  { key: 'weekly', label: 'W' },
]

export default function SymbolDetailPage() {
  const t = useTranslations()
  const params = useParams()
  const symbol = (params?.symbol as string) || ''

  const [frequency, setFrequency] = useState<Frequency>('daily')
  const { data: klineData, isLoading, error } = useKlines(symbol, frequency)

  const bars = klineData?.bars || klineData?.data || []
  const currentPrice = bars.length > 0 ? bars[bars.length - 1].close : null
  const prevPrice = bars.length > 1 ? bars[bars.length - 2].close : currentPrice
  const change = currentPrice !== null && prevPrice !== null ? currentPrice - prevPrice : 0
  const changePct = prevPrice && prevPrice !== 0 ? change / prevPrice : 0

  // Order book — empty by default (live depth requires WS subscription)
  const orderBook: { bids: Level[]; asks: Level[] } = { bids: [], asks: [] }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header with price display */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{symbol}</h1>
            {currentPrice !== null && (
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[18px] font-mono font-semibold text-[var(--foreground)]">
                  {formatPrice(currentPrice)}
                </span>
                <span
                  className={cn(
                    'text-[13px] font-mono',
                    change >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'
                  )}
                >
                  {change >= 0 ? '+' : ''}{formatPrice(change)} ({formatPercent(changePct)})
                </span>
              </div>
            )}
          </div>

          {/* Frequency selector */}
          <div className="flex items-center gap-0.5 bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-sm)] p-0.5">
            {FREQUENCIES.map((f) => (
              <button
                key={f.key}
                onClick={() => setFrequency(f.key)}
                className={cn(
                  'text-[12px] font-medium px-3 py-1 rounded-[var(--radius-sm)] transition-colors',
                  frequency === f.key
                    ? 'bg-[var(--primary)] text-white'
                    : 'text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          </Card>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => window.location.reload()}
              >
                {t('common.retry')}
              </button>
            </div>
          </Card>
        )}

        {/* Chart + Order Book grid */}
        {!isLoading && !error && (
          <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
            {/* Candlestick Chart — 9 cols */}
            <div className="col-span-9">
              <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
                <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">
                  {symbol} &middot; {frequency}
                </h2>
                <CandlestickChart data={bars} />
              </Card>
            </div>

            {/* Order Book — 3 cols */}
            <div className="col-span-3">
              <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
                <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('market.depth')}</h2>
                <OrderBook bids={orderBook.bids} asks={orderBook.asks} />
              </Card>
            </div>
          </div>
        )}

        {/* Empty state (no data) */}
        {!isLoading && !error && !bars.length && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
