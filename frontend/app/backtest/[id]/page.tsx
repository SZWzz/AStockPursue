// frontend/app/backtest/[id]/page.tsx — Backtest detail (Coinbase theme)
'use client'

import { useState, useMemo } from 'react'
import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useBacktest } from '@/hooks'
import { StatCallout } from '@/components/financial/StatCallout'
import { EquityChart } from '@/components/financial/EquityChart'
import { DrawdownChart } from '@/components/financial/DrawdownChart'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { formatPercent, formatDateTime, formatPrice, formatPnL } from '@/lib/utils'

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
  sortino_ratio?: number
  profit_factor?: number
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

  // BD2: Trade table state
  const [sideFilter, setSideFilter] = useState<string>('all')
  const [sortField, setSortField] = useState<'time' | 'symbol' | 'pnl' | 'price'>('time')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const trades: TradeItem[] = detail?.trades || []

  const filteredTrades = useMemo(() => {
    let filtered = trades
    if (sideFilter !== 'all') {
      filtered = filtered.filter((tr) => tr.side === sideFilter)
    }
    return [...filtered].sort((a, b) => {
      let va: any, vb: any
      if (sortField === 'time') {
        va = a.time; vb = b.time
      } else if (sortField === 'symbol') {
        va = a.symbol; vb = b.symbol
      } else if (sortField === 'pnl') {
        va = a.pnl ?? 0; vb = b.pnl ?? 0
      } else if (sortField === 'price') {
        va = a.price; vb = b.price
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [trades, sideFilter, sortField, sortDir])

  const handleSort = (field: 'time' | 'symbol' | 'pnl' | 'price') => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  // BD3: CSV export
  const handleExportCSV = () => {
    if (!trades.length) return
    const headers = [t('trading.symbol'), t('trading.side'), t('trading.price'), t('trading.quantity'), t('portfolio.pnl'), t('signals.timestamp')]
    const rows = trades.map((tr) =>
      [
        tr.symbol,
        tr.side,
        formatPrice(tr.price),
        String(tr.quantity),
        tr.pnl != null ? formatPnL(tr.pnl) : '',
        formatDateTime(tr.time),
      ].join(',')
    )
    const csv = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `backtest-${detail?.id || 'export'}-trades.csv`
    a.click()
    URL.revokeObjectURL(url)
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
            <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{detail.name}</h1>
            <p className="text-[12px] text-[var(--foreground-muted)] mt-0.5">
              {(detail.symbol || detail.strategy) && <>{detail.symbol || detail.strategy} &middot; </>}
              {t('backtest.startDate')}: {formatDateTime(detail.start_date)} &middot; {t('backtest.endDate')}: {formatDateTime(detail.end_date)}
            </p>
          </div>
          {/* BD3: Export button */}
          <Button variant="outline" onClick={handleExportCSV} disabled={!trades.length} className="text-[13px]">
            {t('common.export')} CSV
          </Button>
        </div>

        {/* KPI Cards — StatCallout on white card */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-6">
          <div className="grid grid-cols-6 gap-[var(--grid-gap)]">
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
            {/* BD1: Sortino ratio */}
            {detail.sortino_ratio !== undefined && (
              <StatCallout
                label={t('backtest.sortinoRatio')}
                value={detail.sortino_ratio.toFixed(2)}
              />
            )}
            {/* BD1: Profit factor */}
            {detail.profit_factor !== undefined && (
              <StatCallout
                label={t('backtest.profitFactor')}
                value={detail.profit_factor.toFixed(2)}
              />
            )}
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

        {/* BD2: Trade Log Table */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[18px] font-semibold text-[var(--foreground)]">{t('backtest.tradeLog')}</h2>
            <select
              value={sideFilter}
              onChange={(e) => setSideFilter(e.target.value)}
              className="bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 focus:outline-none focus:border-[var(--primary)]"
            >
              <option value="all">{t('trading.allStatuses')}</option>
              <option value="buy">{t('trading.buy')}</option>
              <option value="sell">{t('trading.sell')}</option>
            </select>
          </div>
          {filteredTrades.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('symbol')}>
                    {t('trading.symbol')} {sortField === 'symbol' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </TableHead>
                  <TableHead>{t('trading.side')}</TableHead>
                  <TableHead className="text-right cursor-pointer select-none" onClick={() => handleSort('price')}>
                    {t('trading.price')} {sortField === 'price' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </TableHead>
                  <TableHead className="text-right">{t('trading.quantity')}</TableHead>
                  <TableHead className="text-right cursor-pointer select-none" onClick={() => handleSort('pnl')}>
                    {t('portfolio.pnl')} {sortField === 'pnl' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </TableHead>
                  <TableHead className="text-right cursor-pointer select-none" onClick={() => handleSort('time')}>
                    {t('signals.timestamp')} {sortField === 'time' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTrades.map((tr) => (
                  <TableRow key={tr.id}>
                    <TableCell className="font-medium">{tr.symbol}</TableCell>
                    <TableCell>{tr.side}</TableCell>
                    <TableCell className="font-mono tabular-nums text-right">{formatPrice(tr.price)}</TableCell>
                    <TableCell className="font-mono tabular-nums text-right">{tr.quantity}</TableCell>
                    <TableCell className={`font-mono tabular-nums text-right ${(tr.pnl ?? 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'}`}>
                      {tr.pnl != null ? formatPnL(tr.pnl) : '--'}
                    </TableCell>
                    <TableCell className="font-mono text-[var(--foreground-muted)] text-right text-[12px]">
                      {formatDateTime(tr.time)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-6">{t('common.noData')}</div>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
