// frontend/app/paper-trading/[id]/page.tsx — Paper trading detail
'use client'

import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { KpiCard } from '@/components/financial/KpiCard'
import { EquityChart } from '@/components/financial/EquityChart'
import { TradeTimeline } from '@/components/financial/TradeTimeline'
import { useWebSocket } from '@/hooks/useWebSocket'
import { formatPercent, formatDateTime } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface TradeItem {
  id: string
  symbol: string
  side: string
  price: number
  quantity: number
  pnl?: number
  time: number
}

interface PaperDetail {
  id: string
  name: string
  strategy: string
  status: string
  initial_capital: number
  equity: number
  pnl: number
  pnl_pct: number
  total_return: number
  max_drawdown: number
  total_trades: number
  equity_curve?: { time: string | number; equity: number }[]
  trades?: TradeItem[]
  created_at: string | number
}

export default function PaperTradingDetailPage() {
  const t = useTranslations()
  const params = useParams()
  const id = params?.id as string

  useWebSocket()

  const { data, isLoading, error } = useSWR(id ? `/api/papertrading/${id}` : null, fetcher)

  const detail: PaperDetail | null = data?.data || data || null

  const handleStart = async () => {
    try {
      await fetch(`/api/papertrading/${id}/start`, { method: 'POST' })
    } catch (e) {
      console.error('Failed to start paper trading', e)
    }
  }

  const handleStop = async () => {
    try {
      await fetch(`/api/papertrading/${id}/stop`, { method: 'POST' })
    } catch (e) {
      console.error('Failed to stop paper trading', e)
    }
  }

  if (isLoading) {
    return (
      <SidebarLayout>
        <div className="flex items-center justify-center h-64 text-[13px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
      </SidebarLayout>
    )
  }

  if (error || !detail) {
    return (
      <SidebarLayout>
        <div className="flex flex-col items-center justify-center h-64 gap-2">
          <div className="text-[13px] text-[var(--down)]">{t('common.error')}</div>
          <button className="text-[13px] underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
            {t('common.retry')}
          </button>
        </div>
      </SidebarLayout>
    )
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-bold text-[var(--foreground)]">{detail.name}</h1>
            <p className="text-[12px] text-[var(--foreground-muted)] mt-0.5">
              {detail.strategy || '--'} &middot; {t('backtest.startDate')}: {formatDateTime(detail.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {detail.status !== 'running' && (
              <button
                onClick={handleStart}
                className="bg-[var(--up)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity"
              >
                Start
              </button>
            )}
            {detail.status === 'running' && (
              <button
                onClick={handleStop}
                className="bg-[var(--down)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity"
              >
                Stop
              </button>
            )}
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <KpiCard
            label={t('portfolio.totalEquity')}
            value={`$${(detail.equity ?? detail.initial_capital ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            direction="up"
          />
          <KpiCard
            label={t('backtest.totalReturn')}
            value={detail.pnl_pct !== undefined ? formatPercent(detail.pnl_pct) : '--'}
            direction={detail.pnl_pct !== undefined && detail.pnl_pct >= 0 ? 'up' : 'down'}
          />
          <KpiCard
            label={t('backtest.maxDrawdown')}
            value={detail.max_drawdown !== undefined ? formatPercent(detail.max_drawdown) : '--'}
            direction="down"
          />
          <KpiCard
            label={t('backtest.totalTrades')}
            value={detail.total_trades !== undefined ? String(detail.total_trades) : '0'}
          />
        </div>

        {/* Chart + Timeline */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('backtest.equityCurve')}</h2>
              <EquityChart data={detail.equity_curve || []} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('backtest.tradeLog')}</h2>
              <TradeTimeline trades={detail.trades || []} />
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
