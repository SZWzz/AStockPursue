// frontend/app/backtest/page.tsx — Backtest list (Coinbase theme)
'use client'

import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useBacktests } from '@/hooks'
import { cn, formatPercent, formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

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
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.backtest')}</h1>
          <Button onClick={() => router.push('/backtest/new')}>
            {t('backtest.new')}
          </Button>
        </div>

        {/* Content */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] overflow-hidden">
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
            <EmptyState
              title={t('common.noData')}
              description={t('backtest.emptyHint') || '还没有回测记录，去创建一个吧'}
              action={{ label: t('backtest.new'), href: '/backtest/new' }}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t('trading.symbol')}</TableHead>
                  <TableHead>{t('backtest.strategy')}</TableHead>
                  <TableHead>{t('backtest.startDate')}</TableHead>
                  <TableHead>{t('backtest.endDate')}</TableHead>
                  <TableHead className="text-right">{t('backtest.totalReturn')}</TableHead>
                  <TableHead className="text-right">{t('backtest.sharpeRatio')}</TableHead>
                  <TableHead className="text-right">{t('backtest.maxDrawdown')}</TableHead>
                  <TableHead className="text-right">{t('backtest.winRate')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {backtests.map((bt) => (
                  <TableRow
                    key={bt.id}
                    onClick={() => router.push(`/backtest/${bt.id}`)}
                    className="cursor-pointer"
                  >
                    <TableCell className="font-medium">{bt.name}</TableCell>
                    <TableCell className="text-[var(--foreground-secondary)]">{bt.strategy || '--'}</TableCell>
                    <TableCell className="font-mono text-[var(--foreground-muted)]">{formatDateTime(bt.start_date)}</TableCell>
                    <TableCell className="font-mono text-[var(--foreground-muted)]">{formatDateTime(bt.end_date)}</TableCell>
                    <TableCell className={cn('font-mono tabular-nums text-right', bt.total_return !== undefined ? (bt.total_return >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]') : 'text-[var(--foreground-secondary)]')}>
                      {bt.total_return !== undefined ? (
                        <span>
                          <span>{bt.total_return >= 0 ? '▲' : '▼'}</span>
                          {' '}{formatPercent(bt.total_return)}
                        </span>
                      ) : '--'}
                    </TableCell>
                    <TableCell className="font-mono tabular-nums text-right text-[var(--foreground-secondary)]">
                      {bt.sharpe_ratio !== undefined ? bt.sharpe_ratio.toFixed(2) : '--'}
                    </TableCell>
                    <TableCell className="font-mono tabular-nums text-right text-[var(--down)]">
                      {bt.max_drawdown !== undefined ? formatPercent(bt.max_drawdown) : '--'}
                    </TableCell>
                    <TableCell className="font-mono tabular-nums text-right text-[var(--foreground-secondary)]">
                      {bt.win_rate !== undefined ? formatPercent(bt.win_rate) : '--'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
