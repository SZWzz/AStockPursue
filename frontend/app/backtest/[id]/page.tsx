// frontend/app/backtest/[id]/page.tsx — Backtest detail (Coinbase theme)
'use client'

import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useBacktest } from '@/hooks'
import { StatCallout } from '@/components/financial/StatCallout'
import { EquityChart } from '@/components/financial/EquityChart'
import { DrawdownChart } from '@/components/financial/DrawdownChart'
import { TradeTimeline } from '@/components/financial/TradeTimeline'
import { formatPercent, formatDateTime } from '@/lib/utils'

interface TradeItem {
  id: string
  symbol: string
  side: string
  price: number
  quantity: number
  pnl?: number
  time: number
}

interface BacktestDetail {
  id: string
  name: string
  strategy: string
  symbol?: string
  start_date: string | number
  end_date: string | number
  frequency: string
  initial_capital: number
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  equity_curve?: { time: string | number; equity: number }[]
  drawdown_curve?: { time: string; drawdown: number }[]
  trades?: TradeItem[]
}

export default function BacktestDetailPage() {
  const t = useTranslations()
  const params = useParams()
  const id = params?.id as string

  const { data, isLoading, error } = useBacktest(id || null)
  const detail: BacktestDetail | null = data?.data || data || null

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
        <div>
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{detail.name}</h1>
          <p className="text-[12px] text-[var(--foreground-muted)] mt-0.5">
            {(detail.symbol || detail.strategy) && <>{detail.symbol || detail.strategy} &middot; </>}
            {t('backtest.startDate')}: {formatDateTime(detail.start_date)} &middot; {t('backtest.endDate')}: {formatDateTime(detail.end_date)}
          </p>
        </div>

        {/* KPI Cards — StatCallout on white card */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-6">
          <div className="grid grid-cols-5 gap-[var(--grid-gap)]">
            <StatCallout
              label={t('backtest.totalReturn')}
              value={detail.total_return !== undefined ? formatPercent(detail.total_return) : '--'}
            />
            <StatCallout
              label={t('backtest.sharpeRatio')}
              value={detail.sharpe_ratio !== undefined ? detail.sharpe_ratio.toFixed(2) : '--'}
            />
            <StatCallout
              label={t('backtest.maxDrawdown')}
              value={detail.max_drawdown !== undefined ? formatPercent(detail.max_drawdown) : '--'}
            />
            <StatCallout
              label={t('backtest.winRate')}
              value={detail.win_rate !== undefined ? formatPercent(detail.win_rate) : '--'}
            />
            <StatCallout
              label={t('backtest.totalTrades')}
              value={detail.total_trades !== undefined ? String(detail.total_trades) : '0'}
            />
          </div>
        </div>

        {/* Equity Curve */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <h2 className="text-[18px] font-semibold mb-4 text-[var(--foreground)]">{t('backtest.equityCurve')}</h2>
          <EquityChart data={detail.equity_curve || []} />
        </div>

        {/* Drawdown Chart */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <h2 className="text-[18px] font-semibold mb-4 text-[var(--foreground)]">{t('analysis.drawdown')}</h2>
          <DrawdownChart data={detail.drawdown_curve || []} />
        </div>

        {/* Trade Log */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <h2 className="text-[18px] font-semibold mb-4 text-[var(--foreground)]">{t('backtest.tradeLog')}</h2>
          <TradeTimeline trades={detail.trades || []} />
        </div>
      </div>
    </SidebarLayout>
  )
}
