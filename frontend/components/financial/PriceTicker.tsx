// frontend/components/financial/PriceTicker.tsx
import { cn } from '@/lib/utils'

interface PriceTickerProps {
  symbol: string
  name?: string
  price: number
  change: number
  changePct: number
  high?: number
  low?: number
  className?: string
}

export function PriceTicker({ symbol, name, price, change, changePct, high, low, className }: PriceTickerProps) {
  const isUp = change >= 0
  return (
    <div className={cn(
      'flex items-center gap-6 px-6 py-4 bg-[var(--surface-1)] rounded-[6px]',
      className
    )}>
      <div className="flex items-baseline gap-2">
        <span className="text-[14px] font-mono font-semibold text-[var(--foreground)]">{symbol}</span>
        {name && <span className="text-[14px] text-[var(--foreground-secondary)]">{name}</span>}
      </div>
      <div className="text-[36px] font-[400] leading-[1.11] tracking-[-0.5px] font-mono tabular-nums text-[var(--foreground)]">
        {price.toFixed(2)}
      </div>
      <div className={cn(
        'flex items-center gap-1 text-[16px] font-mono tabular-nums',
        isUp ? 'text-[var(--up)]' : 'text-[var(--down)]'
      )}>
        <span>{isUp ? '▲' : '▼'}</span>
        <span>{isUp ? '+' : ''}{change.toFixed(2)}</span>
        <span>({isUp ? '+' : ''}{changePct.toFixed(2)}%)</span>
      </div>
      {(high !== undefined && low !== undefined) && (
        <div className="flex items-center gap-4 ml-auto text-[12px] text-[var(--foreground-secondary)]">
          <span>H: <span className="font-mono text-[var(--foreground)]">{high.toFixed(2)}</span></span>
          <span>L: <span className="font-mono text-[var(--foreground)]">{low.toFixed(2)}</span></span>
        </div>
      )}
    </div>
  )
}
