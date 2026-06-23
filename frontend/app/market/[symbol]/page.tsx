// frontend/app/market/[symbol]/page.tsx — Symbol detail
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Skeleton } from '@/components/ui/Skeleton'
import dynamic from 'next/dynamic'
const CandlestickChart = dynamic(() => import('@/components/financial/CandlestickChart').then(mod => mod.CandlestickChart), { ssr: false, loading: () => <Skeleton className="h-[400px] w-full" /> })
import { OrderBook } from '@/components/financial/OrderBook'
import { KpiCard } from '@/components/financial/KpiCard'
import { Card } from '@/components/ui/card'
import { useKlines } from '@/hooks'
import { wsClient } from '@/lib/ws'
import { cn, formatPrice, formatPercent } from '@/lib/utils'


interface Level {
  price: number
  quantity: number
}

type Frequency = '1m' | '5m' | 'daily' | 'weekly' | 'monthly' | 'tick'

const FREQUENCIES: { key: Frequency; label: string; labelKey?: string }[] = [
  { key: '1m', label: '1m' },
  { key: '5m', label: '5m' },
  { key: 'daily', label: 'D' },
  { key: 'weekly', label: 'W' },
  { key: 'monthly', label: 'M' },
  { key: 'tick', label: 'T' },
]

type TabKey = 'chart' | 'fundamentals'

export default function SymbolDetailPage() {
  const t = useTranslations()
  const params = useParams()
  const symbol = (params?.symbol as string) || ''

  const [frequency, setFrequency] = useState<Frequency>('daily')
  const [activeTab, setActiveTab] = useState<TabKey>('chart')
  const [orderBook, setOrderBook] = useState<{ bids: Level[]; asks: Level[] }>({
    bids: [],
    asks: [],
  })

  const { data: klineData, isLoading, error } = useKlines(symbol, frequency)

  const bars = klineData?.bars || klineData?.data || []
  const currentPrice = bars.length > 0 ? bars[bars.length - 1].close : null
  const prevPrice = bars.length > 1 ? bars[bars.length - 2].close : currentPrice
  const change = currentPrice !== null && prevPrice !== null ? currentPrice - prevPrice : 0
  const changePct = prevPrice && prevPrice !== 0 ? change / prevPrice : 0

  // SD3: Fetch fundamentals
  const {
    data: financialsData,
    isLoading: financialsLoading,
    error: financialsError,
  } = useSWR(
    activeTab === 'fundamentals' ? `/api/research/financials?symbol=${symbol}` : null
  )

  const financials = financialsData?.data || financialsData || {}

  // SD1: Subscribe to WS order book
  useEffect(() => {
    if (!symbol) return

    wsClient.subscribe('orderbook', [symbol])

    const unsub = wsClient.on('orderbook', (_channel: string, data: any) => {
      // Data may contain symbol field; match to current symbol
      if (data.symbol === symbol || !data.symbol) {
        const bids: Level[] = (data.bids || []).map((b: any) => ({
          price: b[0] ?? b.price,
          quantity: b[1] ?? b.quantity,
        }))
        const asks: Level[] = (data.asks || []).map((a: any) => ({
          price: a[0] ?? a.price,
          quantity: a[1] ?? a.quantity,
        }))
        setOrderBook({ bids, asks })
      }
    })

    return () => {
      unsub()
      wsClient.unsubscribe('orderbook', [symbol])
    }
  }, [symbol])

  // SD2: Compute volume data for profile
  const maxVolume = bars.length ? Math.max(...bars.map((b: any) => b.volume || 0)) : 0

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
                  {change >= 0 ? '+' : ''}
                  {formatPrice(change)} ({formatPercent(changePct)})
                </span>
              </div>
            )}
          </div>

          {/* SD4: Frequency selector with monthly and tick */}
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

        {/* Tab selector: Chart | Fundamentals */}
        <div className="flex items-center gap-0.5 bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-sm)] p-0.5 w-fit">
          <button
            onClick={() => setActiveTab('chart')}
            className={cn(
              'text-[12px] font-medium px-3 py-1 rounded-[var(--radius-sm)] transition-colors',
              activeTab === 'chart'
                ? 'bg-[var(--primary)] text-white'
                : 'text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
            )}
          >
            {t('market.chart')}
          </button>
          <button
            onClick={() => setActiveTab('fundamentals')}
            className={cn(
              'text-[12px] font-medium px-3 py-1 rounded-[var(--radius-sm)] transition-colors',
              activeTab === 'fundamentals'
                ? 'bg-[var(--primary)] text-white'
                : 'text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
            )}
          >
            {t('market.fundamentals')}
          </button>
        </div>

        {/* Loading state */}
        {isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
              {t('common.loading')}
            </div>
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

        {/* Chart Tab */}
        {activeTab === 'chart' && !isLoading && !error && (
          <div className="space-y-3">
            {/* Chart + Order Book grid */}
            <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
              {/* Candlestick Chart — 9 cols */}
              <div className="col-span-9">
                <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
                  <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">
                    {symbol} &middot; {frequency}
                  </h2>
                  <CandlestickChart data={bars} />
                </Card>

                {/* SD2: Volume Profile */}
                {bars.length > 0 && (
                  <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)] mt-[var(--grid-gap)]">
                    <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">
                      {t('market.volumeProfile')}
                    </h2>
                    <div className="flex items-end gap-[2px] h-16">
                      {bars.slice(-60).map((b: any, i: number) => {
                        const vol = b.volume || 0
                        const height = maxVolume > 0 ? (vol / maxVolume) * 100 : 0
                        const barColor =
                          (b.close || 0) >= (b.open || 0) ? 'var(--up)' : 'var(--down)'
                        return (
                          <div
                            key={i}
                            className="flex-1 rounded-t-[2px] transition-all"
                            style={{
                              height: `${Math.max(1, height)}%`,
                              backgroundColor: barColor,
                              opacity: 0.6,
                            }}
                            title={`Vol: ${vol.toLocaleString()}`}
                          />
                        )
                      })}
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-[10px] text-[var(--foreground-muted)]">
                        {bars[Math.max(0, bars.length - 60)]?.time || ''}
                      </span>
                      <span className="text-[10px] text-[var(--foreground-muted)]">
                        {bars[bars.length - 1]?.time || ''}
                      </span>
                    </div>
                  </Card>
                )}
              </div>

              {/* Order Book — 3 cols */}
              <div className="col-span-3">
                <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
                  <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">
                    {t('market.depth')}
                  </h2>
                  <OrderBook bids={orderBook.bids} asks={orderBook.asks} />
                </Card>
              </div>
            </div>
          </div>
        )}

        {/* SD3: Fundamentals Tab */}
        {activeTab === 'fundamentals' && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
            <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-3">
              {t('market.fundamentals')}
            </h2>

            {financialsLoading && (
              <div className="text-[13px] text-[var(--foreground-muted)] text-center py-8">
                {t('common.loading')}
              </div>
            )}

            {financialsError && !financialsLoading && (
              <div className="text-[13px] text-[var(--down)] text-center py-8">
                {t('common.error')}
              </div>
            )}

            {!financialsLoading && !financialsError && financialsData && (
              <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
                <KpiCard
                  label={t('market.pe')}
                  value={
                    financials.pe_ratio !== undefined
                      ? financials.pe_ratio.toFixed(2)
                      : '--'
                  }
                />
                <KpiCard
                  label={t('market.pb')}
                  value={
                    financials.pb_ratio !== undefined
                      ? financials.pb_ratio.toFixed(2)
                      : '--'
                  }
                />
                <KpiCard
                  label={t('research.roe')}
                  value={
                    financials.roe !== undefined
                      ? formatPercent(financials.roe / 100)
                      : '--'
                  }
                  direction={
                    financials.roe !== undefined
                      ? financials.roe >= 0
                        ? 'up'
                        : 'down'
                      : undefined
                  }
                />
                <KpiCard
                  label={t('research.eps')}
                  value={
                    financials.eps !== undefined
                      ? financials.eps.toFixed(2)
                      : '--'
                  }
                />
              </div>
            )}

            {!financialsLoading && !financialsError && !financialsData && (
              <div className="text-[13px] text-[var(--foreground-muted)] text-center py-8">
                {t('market.enterSymbolHint')}
              </div>
            )}
          </Card>
        )}

        {/* Empty state (no data) */}
        {!isLoading && !error && !bars.length && activeTab === 'chart' && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
              {t('common.noData')}
            </div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
