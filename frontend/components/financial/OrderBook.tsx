// frontend/components/financial/OrderBook.tsx
import { formatPrice, formatVolume } from '@/lib/utils'

interface Level { price: number; quantity: number }

export function OrderBook({ bids, asks }: { bids: Level[]; asks: Level[] }) {
  const maxQty = Math.max(...bids.map(b => b.quantity), ...asks.map(a => a.quantity), 1)

  const renderSide = (levels: Level[], color: string, label: string) => (
    <div>
      <div className="text-[11px] text-[var(--foreground-muted)] px-1 py-0.5 border-b border-[var(--border-subtle)]">{label}</div>
      {levels.slice(0, 10).map((l, i) => (
        <div key={i} className="flex justify-between px-1 py-0.5 relative">
          <div className="absolute inset-0 opacity-10" style={{ backgroundColor: color, width: `${(l.quantity / maxQty) * 100}%`, right: 0, left: 'auto' }} />
          <span className="relative z-10" style={{ color }}>{formatPrice(l.price)}</span>
          <span className="text-[var(--foreground-secondary)] relative z-10">{formatVolume(l.quantity)}</span>
        </div>
      ))}
    </div>
  )

  return (
    <div className="grid grid-cols-2 gap-0 text-[11px] font-mono">
      {renderSide(bids, 'var(--up)', 'Bid')}
      {renderSide(asks, 'var(--down)', 'Ask')}
    </div>
  )
}
