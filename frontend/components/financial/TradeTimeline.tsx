// frontend/components/financial/TradeTimeline.tsx
import { cn, formatPrice, formatPnL, formatDateTime } from '@/lib/utils'
import { useTranslations } from 'next-intl'

interface TradeItem { id: string; symbol: string; side: string; price: number; quantity: number; pnl?: number; time: number }

export function TradeTimeline({ trades }: { trades: TradeItem[] }) {
  const t = useTranslations()
  if (!trades.length) return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-8">{t('common.noData')}</div>

  return (
    <div className="space-y-0">
      {trades.map(trade => (
        <div key={trade.id} className="flex items-center gap-3 py-1.5 px-2 border-b border-[var(--border-subtle)] last:border-0 text-[12px]">
          <span className={cn('w-8 font-medium', trade.side === 'buy' ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{trade.side.toUpperCase()}</span>
          <span className="font-mono w-20">{trade.symbol}</span>
          <span className="font-mono w-16 text-right">{formatPrice(trade.price)}</span>
          <span className="font-mono w-12 text-right text-[var(--foreground-secondary)]">{trade.quantity}</span>
          {trade.pnl !== undefined && (
            <span className={cn('font-mono w-20 text-right', trade.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>{formatPnL(trade.pnl)}</span>
          )}
          <span className="text-[var(--foreground-muted)] ml-auto">{formatDateTime(trade.time)}</span>
        </div>
      ))}
    </div>
  )
}
