// frontend/components/financial/ScreenerGrid.tsx
import { useTranslations } from 'next-intl'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn, formatPrice, formatPercent } from '@/lib/utils'

interface Row { symbol: string; name?: string; price: number; change_pct: number; volume: number }

export function ScreenerGrid({ data }: { data: Row[] }) {
  const t = useTranslations()
  if (!data.length) return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-8">{t('common.noData')}</div>
  return (
    <Table>
      <TableHeader>
        <TableRow className="border-[var(--border-subtle)] hover:bg-transparent">
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('trading.symbol')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('trading.price')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('screener.change')}</TableHead>
          <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('screener.volume')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map(r => (
          <TableRow key={r.symbol} className="border-[var(--border-subtle)] hover:bg-[var(--surface-3)]">
            <TableCell className="text-[13px] font-mono font-medium py-1.5">{r.symbol}</TableCell>
            <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(r.price)}</TableCell>
            <TableCell className={cn('text-[13px] font-mono text-right py-1.5', r.change_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPercent(r.change_pct / 100)}</TableCell>
            <TableCell className="text-[13px] font-mono text-right text-[var(--foreground-secondary)] py-1.5">{r.volume.toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
