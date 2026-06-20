// frontend/components/financial/OrderBook.tsx
import { formatPrice, formatVolume } from '@/lib/utils'

interface Level { price: number; quantity: number }

export function OrderBook({ bids, asks }: { bids: Level[]; asks: Level[] }) {
  const displayAsks = asks.slice(0, 10)
  const displayBids = bids.slice(0, 10)

  const maxAskQty = Math.max(...displayAsks.map(l => l.quantity), 1)
  const maxBidQty = Math.max(...displayBids.map(l => l.quantity), 1)

  // Build cumulative data from best price outward
  let bidCum = 0
  const bidRows = displayBids.map(l => {
    bidCum += l.quantity
    return { ...l, cumulative: bidCum, depthPct: (l.quantity / maxBidQty) * 100 }
  })

  let askCum = 0
  const askRows = displayAsks.map(l => {
    askCum += l.quantity
    return { ...l, cumulative: askCum, depthPct: (l.quantity / maxAskQty) * 100 }
  })

  const bestAsk = displayAsks.length > 0 ? displayAsks[0].price : 0
  const bestBid = displayBids.length > 0 ? displayBids[0].price : 0
  const spread = bestAsk - bestBid
  const spreadPct = bestAsk > 0 ? (spread / bestAsk) * 100 : 0

  function renderRow(
    l: { price: number; quantity: number; cumulative: number; depthPct: number },
    color: string,
    key: number
  ) {
    return (
      <div key={key} className="relative">
        <div className="absolute right-0 top-0 h-full opacity-[0.08]" style={{ backgroundColor: color, width: `${l.depthPct}%` }} />
        <div className="relative flex items-center h-5 px-1 text-[14px] font-mono">
          <span className="w-1/3" style={{ color }}>{formatPrice(l.price)}</span>
          <span className="w-1/3 text-right text-[var(--foreground-secondary)]">{formatVolume(l.quantity)}</span>
          <span className="w-1/3 text-right text-[var(--foreground-muted)]">{formatVolume(l.cumulative)}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="text-[14px] font-mono">
      {/* Header */}
      <div className="flex items-center h-5 px-1 text-[11px] text-[var(--foreground-muted)] border-b border-[var(--border-subtle)]">
        <span className="w-1/3">Price</span>
        <span className="w-1/3 text-right">Qty</span>
        <span className="w-1/3 text-right">Total</span>
      </div>
      {/* Asks — reversed so highest price appears at the top */}
      {[...askRows].reverse().map((l, i) => renderRow(l, 'var(--down)', i))}
      {/* Spread */}
      <div className="flex items-center h-5 px-1 border-t border-b border-[var(--border-subtle)] text-[12px]">
        <span className="text-[var(--foreground-secondary)]">Spread {formatPrice(spread)}</span>
        <span className="text-[var(--foreground-muted)] ml-1">({spreadPct.toFixed(3)}%)</span>
      </div>
      {/* Bids — best bid at top */}
      {bidRows.map((l, i) => renderRow(l, 'var(--up)', i + 100))}
    </div>
  )
}
