// frontend/components/backtest/BacktestContent.tsx
'use client'

import { useState, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { useBacktests } from '@/hooks'
import { cn, formatPercent, formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
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

export function BacktestContent() {
  const t = useTranslations()
  const router = useRouter()
  const { data, isLoading, error } = useBacktests()

  const [searchQuery, setSearchQuery] = useState('')
  const [startDateFilter, setStartDateFilter] = useState('')
  const [endDateFilter, setEndDateFilter] = useState('')

  const backtests: BacktestSummary[] = data?.backtests || data?.data || data || []

  // BL1: Filter backtests by name/strategy and date range
  const filteredBacktests = useMemo(() => {
    return backtests.filter((bt) => {
      const matchesSearch =
        !searchQuery ||
        bt.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        bt.strategy?.toLowerCase().includes(searchQuery.toLowerCase())

      let matchesStartDate = true
      let matchesEndDate = true

      if (startDateFilter) {
        const btStart = typeof bt.start_date === 'number'
          ? new Date(bt.start_date * 1000)
          : new Date(bt.start_date)
        matchesStartDate = btStart >= new Date(startDateFilter)
      }

      if (endDateFilter) {
        const btEnd = typeof bt.end_date === 'number'
          ? new Date(bt.end_date * 1000)
          : new Date(bt.end_date)
        matchesEndDate = btEnd <= new Date(endDateFilter)
      }

      return matchesSearch && matchesStartDate && matchesEndDate
    })
  }, [backtests, searchQuery, startDateFilter, endDateFilter])

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.backtest')}</h1>
        <Button onClick={() => router.push('/backtest/new')}>
          {t('backtest.new')}
        </Button>
      </div>

      {/* BL1: Search and date filter */}
      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={t('backtest.searchByName')}
          className="h-9 rounded-[6px] border border-[var(--border)] px-3 text-[13px] w-56 bg-white placeholder:text-[var(--foreground-muted)]"
        />
        <span className="text-[12px] text-[var(--foreground-muted)]">{t('backtest.filterByDate')}:</span>
        <input
          type="date"
          value={startDateFilter}
          onChange={(e) => setStartDateFilter(e.target.value)}
          className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[12px] bg-white"
        />
        <span className="text-[12px] text-[var(--foreground-muted)]">{t('common.to')}</span>
        <input
          type="date"
          value={endDateFilter}
          onChange={(e) => setEndDateFilter(e.target.value)}
          className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[12px] bg-white"
        />
        {(searchQuery || startDateFilter || endDateFilter) && (
          <button
            onClick={() => {
              setSearchQuery('')
              setStartDateFilter('')
              setEndDateFilter('')
            }}
            className="text-[12px] text-[var(--foreground-secondary)] hover:text-[var(--foreground)]"
          >
            {t('common.clearFilters')}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="bg-white border border-[var(--border)] rounded-[6px] overflow-hidden">
        {isLoading ? (
          <SkeletonTable rows={5} cols={8} />
        ) : error ? (
          <div className="text-[13px] text-[var(--down)] text-center py-12">
            {t('common.error')}
            <button className="ml-2 underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
              {t('common.retry')}
            </button>
          </div>
        ) : !filteredBacktests.length ? (
          <EmptyState
            title={t('common.noData')}
            description={t('backtest.emptyHint')}
            action={{ label: t('backtest.new'), href: '/backtest/new' }}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>{t('backtest.name')}</TableHead>
                <TableHead>{t('backtest.strategy')}</TableHead>
                <TableHead>{t('backtest.startDate')}</TableHead>
                <TableHead>{t('backtest.endDate')}</TableHead>
                <TableHead className="text-right">{t('backtest.status')}</TableHead>
                <TableHead className="text-right">{t('backtest.totalReturn')}</TableHead>
                <TableHead className="text-right">{t('backtest.sharpeRatio')}</TableHead>
                <TableHead className="text-right">{t('backtest.maxDrawdown')}</TableHead>
                <TableHead className="text-right">{t('backtest.winRate')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredBacktests.map((bt) => (
                <TableRow
                  key={bt.id}
                  onClick={() => router.push(`/backtest/${bt.id}`)}
                  className="cursor-pointer"
                >
                  <TableCell className="font-medium">{bt.name}</TableCell>
                  <TableCell className="text-[var(--foreground-secondary)]">{bt.strategy || '--'}</TableCell>
                  <TableCell className="font-mono text-[var(--foreground-muted)]">{formatDateTime(bt.start_date)}</TableCell>
                  <TableCell className="font-mono text-[var(--foreground-muted)]">{formatDateTime(bt.end_date)}</TableCell>
                  <TableCell className="text-right text-[var(--foreground-muted)]">{t('status.filled')}</TableCell>
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
  )
}
