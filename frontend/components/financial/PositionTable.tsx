// frontend/components/financial/PositionTable.tsx
'use client'

import { useTranslations } from 'next-intl'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { usePositions } from '@/hooks'
import { formatPrice, formatPnL, formatPercent, cn } from '@/lib/utils'

export function PositionTable() {
  const t = useTranslations()
  const { data, error, isLoading } = usePositions()

  if (isLoading) return <div className="text-[14px] text-[var(--foreground-secondary)] p-6">Loading positions...</div>
  if (error) return <div className="text-[14px] text-[var(--destructive)] p-6">Failed to load positions</div>
  const positions = data?.positions || []

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('portfolio.symbol')}</TableHead>
          <TableHead className="text-right">{t('portfolio.position')}</TableHead>
          <TableHead className="text-right">{t('portfolio.entryPrice')}</TableHead>
          <TableHead className="text-right">{t('portfolio.currentPrice')}</TableHead>
          <TableHead className="text-right">{t('portfolio.pnl')}</TableHead>
          <TableHead className="text-right">{t('portfolio.pnlPct')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {positions.length === 0 ? (
          <TableRow>
            <TableCell colSpan={6} className="text-center text-[14px] text-[var(--foreground-secondary)] h-20">
              {t('common.noData')}
            </TableCell>
          </TableRow>
        ) : (
          positions.map((pos: any) => (
            <TableRow key={pos.symbol}>
              <TableCell className="font-mono font-medium">{pos.symbol}</TableCell>
              <TableCell className="font-mono text-right">{pos.size}</TableCell>
              <TableCell className="font-mono text-right">{formatPrice(pos.entry_price)}</TableCell>
              <TableCell className="font-mono text-right">{formatPrice(pos.current_price)}</TableCell>
              <TableCell className={cn('font-mono text-right tabular-nums', pos.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                {pos.pnl > 0 ? '▲ ' : '▼ '}{formatPnL(pos.pnl)}
              </TableCell>
              <TableCell className={cn('font-mono text-right tabular-nums', pos.pnl_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                {pos.pnl_pct > 0 ? '▲ ' : '▼ '}{formatPercent(Math.abs(pos.pnl_pct || 0))}%
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
