// frontend/components/financial/ScreenerGrid.tsx
import { memo } from 'react'
import { useTranslations } from 'next-intl'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn, formatPrice, formatPercent } from '@/lib/utils'
import type { MarketRow } from '@/types'

/**
 * Screener row type — picks fields used by the grid from MarketRow
 * plus screener-specific score & rank.
 */
export type ScreenerRow = Pick<MarketRow, 'symbol' | 'price' | 'change_pct' | 'volume'> & {
  name?: string
  score?: number
  rank?: number
}

interface ScreenerGridProps {
  data: ScreenerRow[]
  onRowClick?: (symbol: string) => void
  mode?: 'filter' | 'rank' | 'score'
  actionLabel?: string
  onAction?: (symbol: string) => void
}

const ScreenerRow = memo(function ScreenerRow({
  row,
  index,
  mode,
  onRowClick,
  actionLabel,
  onAction,
}: {
  row: ScreenerRow
  index: number
  mode: 'filter' | 'rank' | 'score'
  onRowClick?: (symbol: string) => void
  actionLabel?: string
  onAction?: (symbol: string) => void
}) {
  return (
    <TableRow
      className={cn(
        'border-[var(--border-subtle)] hover:bg-[var(--surface-3)]',
        onRowClick && 'cursor-pointer'
      )}
      onClick={() => onRowClick?.(row.symbol)}
    >
      {mode === 'rank' && (
        <TableCell className="text-[12px] font-mono text-center text-[var(--foreground-muted)] py-1.5">
          {row.rank ?? index + 1}
        </TableCell>
      )}
      {mode === 'score' && (
        <TableCell className="text-[12px] font-mono text-center py-1.5">
          {row.score !== undefined ? (
            <div className="flex items-center gap-1">
              <div className="flex-1 h-1.5 bg-[var(--surface-3)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[var(--primary)] rounded-full transition-all"
                  style={{ width: `${Math.min(100, Math.max(0, row.score))}%` }}
                />
              </div>
              <span className="text-[11px] text-[var(--foreground-muted)]">{row.score.toFixed(0)}</span>
            </div>
          ) : (
            '--'
          )}
        </TableCell>
      )}
      <TableCell className="text-[13px] font-mono font-medium py-1.5">
        {row.symbol}
      </TableCell>
      <TableCell className="text-[13px] font-mono text-right py-1.5">
        {formatPrice(row.price)}
      </TableCell>
      <TableCell
        className={cn(
          'text-[13px] font-mono text-right py-1.5',
          row.change_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'
        )}
      >
        {formatPercent(row.change_pct)}
      </TableCell>
      <TableCell className="text-[13px] font-mono text-right text-[var(--foreground-secondary)] py-1.5">
        {row.volume.toLocaleString()}
      </TableCell>
      {actionLabel && onAction && (
        <TableCell className="py-1.5 text-right">
          <button
            onClick={(e) => { e.stopPropagation(); onAction(row.symbol) }}
            className="text-[12px] font-medium text-[var(--primary)] hover:underline"
          >
            {actionLabel}
          </button>
        </TableCell>
      )}
    </TableRow>
  )
})

export function ScreenerGrid({ data, onRowClick, mode = 'filter', actionLabel, onAction }: ScreenerGridProps) {
  const t = useTranslations()
  if (!data.length)
    return (
      <div className="text-[12px] text-[var(--foreground-muted)] text-center py-8">
        {t('common.noData')}
      </div>
    )

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-[var(--border-subtle)] hover:bg-transparent">
          {mode === 'rank' && (
            <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 w-12 text-center">
              #
            </TableHead>
          )}
          {mode === 'score' && (
            <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 w-16 text-center">
              {t('screener.score')}
            </TableHead>
          )}
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">
            {t('trading.symbol')}
          </TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">
            {t('trading.price')}
          </TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">
            {t('screener.change')}
          </TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">
            {t('screener.volume')}
          </TableHead>
          {actionLabel && (
            <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right w-16">{t('common.actions')}</TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((r, i) => (
          <ScreenerRow key={r.symbol} row={r} index={i} mode={mode} onRowClick={onRowClick} actionLabel={actionLabel} onAction={onAction} />
        ))}
      </TableBody>
    </Table>
  )
}
