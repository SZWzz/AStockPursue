// frontend/app/backtest/page.tsx — Backtest list
'use client'

import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useBacktests } from '@/hooks'
import { cn, formatPercent, formatDateTime } from '@/lib/utils'
import { Card } from '@/components/ui/card'

interface BacktestSummary {
  id: string
  name: string
  strategy: string
  start_date: string | number
  end_date: string | number
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
}

export default function BacktestListPage() {
  const t = useTranslations()
  const router = useRouter()
  const { data, isLoading, error } = useBacktests()

  const backtests: BacktestSummary[] = data?.backtests || data?.data || data || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.backtest')}</h1>
          <button
            onClick={() => router.push('/backtest/new')}
            className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity"
          >
            {t('backtest.new')}
          </button>
        </div>

        {/* Content */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
          {isLoading ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          ) : error ? (
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button className="ml-2 underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
                {t('common.retry')}
              </button>
            </div>
          ) : !backtests.length ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                    <th className="text-left py-2.5 px-4 font-medium">{t('trading.symbol')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('backtest.strategy')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('backtest.startDate')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('backtest.endDate')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">{t('backtest.totalReturn')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">{t('backtest.sharpeRatio')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">{t('backtest.maxDrawdown')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">{t('backtest.winRate')}</th>
                  </tr>
                </thead>
                <tbody>
                  {backtests.map((bt) => (
                    <tr
                      key={bt.id}
                      onClick={() => router.push(`/backtest/${bt.id}`)}
                      className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-3)] cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-4 text-[13px] font-medium text-[var(--foreground)]">{bt.name}</td>
                      <td className="py-2.5 px-4 text-[13px] text-[var(--foreground-secondary)]">{bt.strategy || '--'}</td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-muted)]">{formatDateTime(bt.start_date)}</td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-muted)]">{formatDateTime(bt.end_date)}</td>
                      <td className={cn('py-2.5 px-4 text-[13px] font-mono tabular-nums text-right', bt.total_return !== undefined ? (bt.total_return >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]') : 'text-[var(--foreground-secondary)]')}>
                        {bt.total_return !== undefined ? formatPercent(bt.total_return) : '--'}
                      </td>
                      <td className="py-2.5 px-4 text-[13px] font-mono tabular-nums text-right text-[var(--foreground-secondary)]">
                        {bt.sharpe_ratio !== undefined ? bt.sharpe_ratio.toFixed(2) : '--'}
                      </td>
                      <td className="py-2.5 px-4 text-[13px] font-mono tabular-nums text-right text-[var(--down)]">
                        {bt.max_drawdown !== undefined ? formatPercent(bt.max_drawdown) : '--'}
                      </td>
                      <td className="py-2.5 px-4 text-[13px] font-mono tabular-nums text-right text-[var(--foreground-secondary)]">
                        {bt.win_rate !== undefined ? formatPercent(bt.win_rate) : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </SidebarLayout>
  )
}
