// frontend/components/financial/MarketRow.tsx
import { cn } from '@/lib/utils'
import { ChevronRight } from 'lucide-react'

interface MarketRowProps {
  symbol: string
  name: string
  price: number | string
  changePct: number
  onClick?: () => void
}

export function MarketRow({ symbol, name, price, changePct, onClick }: MarketRowProps) {
  const isUp = changePct >= 0
  return (
    <div
      onClick={onClick}
      className={cn(
        'flex items-center h-12 px-4 border-b border-[var(--border-subtle)] cursor-pointer transition-colors hover:bg-[var(--surface-1)]',
        'last:border-b-0'
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-mono font-medium text-[var(--foreground)]">{symbol}</div>
        <div className="text-[12px] text-[var(--foreground-secondary)] truncate">{name}</div>
      </div>
      <div className="text-right min-w-[80px]">
        <div className="text-[14px] font-mono text-[var(--foreground)]">{price}</div>
      </div>
      <div className={cn(
        'text-right min-w-[90px] text-[14px] font-mono tabular-nums',
        isUp ? 'text-[var(--up)]' : 'text-[var(--down)]'
      )}>
        {isUp ? '▲ ' : '▼ '}{Math.abs(changePct).toFixed(2)}%
      </div>
      <ChevronRight className="w-4 h-4 text-[var(--foreground-muted)] ml-2 shrink-0" />
    </div>
  )
}
