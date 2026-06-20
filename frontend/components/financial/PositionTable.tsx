// frontend/components/financial/PositionTable.tsx
'use client'

import { useTranslations } from 'next-intl'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { usePositions } from '@/hooks'
import { formatPrice, formatPnL, formatPercent, cn } from '@/lib/utils'

export function PositionTable() {
  const t = useTranslations()
  const { data, error, isLoading } = usePositions()

  if (isLoading) return <div className="text-[12px] text-[var(--foreground-muted)] p-4">Loading positions...</div>
  if (error) return <div className="text-[12px] text-[var(--destructive)] p-4">Failed to load positions</div>
  const positions = data?.positions || []

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-[var(--border-subtle)] hover:bg-transparent">
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('portfolio.symbol')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.position')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.entryPrice')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.currentPrice')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.pnl')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('portfolio.pnlPct')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {positions.length === 0 ? (
          <TableRow className="border-[var(--border-subtle)]">
            <TableCell colSpan={6} className="text-center text-[12px] text-[var(--foreground-muted)] h-16">{t('common.noData')}</TableCell>
          </TableRow>
        ) : (
          positions.map((pos: any) => (
            <TableRow key={pos.symbol} className="border-[var(--border-subtle)] hover:bg-[var(--surface-3)]">
              <TableCell className="text-[13px] font-mono font-medium py-1.5">{pos.symbol}</TableCell>
              <TableCell className="text-[13px] font-mono text-right py-1.5">{pos.size}</TableCell>
              <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(pos.entry_price)}</TableCell>
              <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(pos.current_price)}</TableCell>
              <TableCell className={cn('text-[13px] font-mono text-right py-1.5', pos.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPnL(pos.pnl)}</TableCell>
              <TableCell className={cn('text-[13px] font-mono text-right py-1.5', pos.pnl_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPercent(pos.pnl_pct || 0)}</TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
