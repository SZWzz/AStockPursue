// frontend/components/financial/PositionTable.tsx
'use client'

import { useState, useRef, useCallback, memo } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { usePositions } from '@/hooks'
import { formatPrice, formatPnL, formatPercent, cn } from '@/lib/utils'
import { X } from 'lucide-react'

export const PositionTable = memo(function PositionTable() {
  const t = useTranslations()
  const { data, error, isLoading, mutate } = usePositions()
  const [closing, setClosing] = useState<string | null>(null)
  const [confirmClose, setConfirmClose] = useState<any | null>(null)

  // Virtual scroll state
  const scrollRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const ROW_HEIGHT = 37
  const HEADER_HEIGHT = 37
  const BUFFER = 5

  const onScroll = useCallback(() => {
    if (scrollRef.current) {
      setScrollTop(scrollRef.current.scrollTop)
    }
  }, [])

  if (isLoading) return <div className="text-[14px] text-[var(--foreground-secondary)] p-6">{t('common.loading')}</div>
  if (error) return <div className="text-[14px] text-[var(--destructive)] p-6">{t('common.error')}</div>

  const portfolio = data
  const positions = portfolio?.positions || []
  const totalEquity = portfolio?.total_value ?? portfolio?.equity ?? 0
  const cash = portfolio?.cash ?? portfolio?.available ?? 0

  // PO2: Aggregate stats
  const totalMarketValue = positions.reduce((sum: number, p: any) => {
    return sum + (p.size || 0) * (p.current_price || 0)
  }, 0)
  const buyingPower = cash
  const totalPnL = positions.reduce((sum: number, p: any) => sum + (p.pnl || 0), 0)
  const exposure = totalEquity > 0 ? (totalMarketValue / totalEquity) * 100 : 0

  // PO1: Close position — show confirmation dialog first
  const requestClose = (pos: any) => {
    setConfirmClose(pos)
  }

  const handleClose = async () => {
    const pos = confirmClose
    if (!pos) return
    const symbol = pos.symbol
    if (!symbol) return
    setClosing(symbol)
    setConfirmClose(null)
    try {
      const body = JSON.stringify({
        symbol,
        side: pos.size > 0 ? 'sell' : 'buy',
        type: 'market',
        price: pos.current_price || 0,
        quantity: Math.abs(pos.size || 0),
      })
      const res = await fetch('/api/trading/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      })
      if (res.ok) {
        toast.success(t('portfolio.closeSuccess') || `Position ${symbol} closed`)
        mutate()
      } else {
        const err = await res.json().catch(() => ({}))
        toast.error((err as any)?.error || t('common.error'))
      }
    } catch {
      toast.error(t('common.error'))
    } finally {
      setClosing(null)
    }
  }

  return (
    <div>
      {/* PO2: Aggregate stats cards */}
      {positions.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div className="bg-[var(--surface-1)] rounded-[6px] p-3">
            <div className="text-[10px] text-[var(--foreground-muted)] uppercase tracking-wide">{t('portfolio.totalEquity')}</div>
            <div className="text-[16px] font-semibold mt-0.5">{formatPnL(totalEquity)}</div>
          </div>
          <div className="bg-[var(--surface-1)] rounded-[6px] p-3">
            <div className="text-[10px] text-[var(--foreground-muted)] uppercase tracking-wide">{t('portfolio.available')}</div>
            <div className="text-[16px] font-semibold mt-0.5">{formatPnL(buyingPower)}</div>
          </div>
          <div className="bg-[var(--surface-1)] rounded-[6px] p-3">
            <div className="text-[10px] text-[var(--foreground-muted)] uppercase tracking-wide">{t('portfolio.exposure') || 'Exposure'}</div>
            <div className={cn('text-[16px] font-semibold mt-0.5', totalPnL > 0 ? 'text-[var(--up)]' : totalPnL < 0 ? 'text-[var(--down)]' : '')}>
              {formatPnL(totalPnL)}
            </div>
          </div>
          <div className="bg-[var(--surface-1)] rounded-[6px] p-3">
            <div className="text-[10px] text-[var(--foreground-muted)] uppercase tracking-wide">{t('portfolio.margin')}</div>
            <div className="text-[16px] font-semibold mt-0.5">{exposure.toFixed(1)}%</div>
          </div>
        </div>
      )}
      {positions.length > 50 ? (
        /* Virtual scrolled container */
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="overflow-auto border border-[var(--border-default)] rounded-[6px]"
          style={{ maxHeight: 400 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('portfolio.symbol')}</TableHead>
                <TableHead className="text-right">{t('portfolio.position')}</TableHead>
                <TableHead className="text-right">{t('portfolio.entryPrice')}</TableHead>
                <TableHead className="text-right">{t('portfolio.currentPrice')}</TableHead>
                <TableHead className="text-right">{t('portfolio.pnl')}</TableHead>
                <TableHead className="text-right">{t('portfolio.pnlPct')}</TableHead>
                <TableHead className="text-right">{t('common.createOrder') || 'Actions'}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(() => {
                if (positions.length === 0) {
                  return (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-[14px] text-[var(--foreground-secondary)] h-20">
                        {t('common.noData')}
                      </TableCell>
                    </TableRow>
                  )
                }
                const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - BUFFER)
                const visibleCount = Math.ceil(400 / ROW_HEIGHT) + BUFFER * 2
                const endIdx = Math.min(positions.length, startIdx + visibleCount)
                return (
                  <>
                    <tr style={{ height: startIdx * ROW_HEIGHT }} />
                    {positions.slice(startIdx, endIdx).map((pos: any) => (
                      <TableRow key={pos.symbol}>
                        <TableCell className="font-mono font-medium" style={{ height: ROW_HEIGHT }}>{pos.symbol}</TableCell>
                        <TableCell className="font-mono text-right" style={{ height: ROW_HEIGHT }}>{pos.size}</TableCell>
                        <TableCell className="font-mono text-right" style={{ height: ROW_HEIGHT }}>{formatPrice(pos.entry_price)}</TableCell>
                        <TableCell className="font-mono text-right" style={{ height: ROW_HEIGHT }}>{formatPrice(pos.current_price)}</TableCell>
                        <TableCell className={cn('font-mono text-right tabular-nums', pos.pnl > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')} style={{ height: ROW_HEIGHT }}>
                          {pos.pnl > 0 ? '▲ ' : '▼ '}{formatPnL(pos.pnl)}
                        </TableCell>
                        <TableCell className={cn('font-mono text-right tabular-nums', pos.pnl_pct > 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')} style={{ height: ROW_HEIGHT }}>
                          {pos.pnl_pct > 0 ? '▲ ' : '▼ '}{formatPercent(Math.abs(pos.pnl_pct || 0))}%
                        </TableCell>
                        <TableCell className="text-right" style={{ height: ROW_HEIGHT }}>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => requestClose(pos)}
                            disabled={closing === pos.symbol}
                            className="h-7 px-2 text-[11px] text-[var(--down)] hover:text-[var(--down)] hover:bg-[var(--down)]/10"
                          >
                            <X className="w-3.5 h-3.5 mr-1" />
                            {closing === pos.symbol ? '...' : t('portfolio.close') || 'Close'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    <tr style={{ height: (positions.length - endIdx) * ROW_HEIGHT }} />
                  </>
                )
              })()}
            </TableBody>
          </Table>
        </div>
      ) : (
        /* Normal table for <= 50 items */
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('portfolio.symbol')}</TableHead>
            <TableHead className="text-right">{t('portfolio.position')}</TableHead>
            <TableHead className="text-right">{t('portfolio.entryPrice')}</TableHead>
            <TableHead className="text-right">{t('portfolio.currentPrice')}</TableHead>
            <TableHead className="text-right">{t('portfolio.pnl')}</TableHead>
            <TableHead className="text-right">{t('portfolio.pnlPct')}</TableHead>
            <TableHead className="text-right">{t('common.createOrder') || 'Actions'}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {positions.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-[14px] text-[var(--foreground-secondary)] h-20">
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
                {/* PO1: Close position button */}
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => requestClose(pos)}
                    disabled={closing === pos.symbol}
                    className="h-7 px-2 text-[11px] text-[var(--down)] hover:text-[var(--down)] hover:bg-[var(--down)]/10"
                  >
                    <X className="w-3.5 h-3.5 mr-1" />
                    {closing === pos.symbol ? '...' : t('portfolio.close') || 'Close'}
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      )}

      {/* Confirmation Dialog */}
      <Dialog open={!!confirmClose} onOpenChange={(open) => { if (!open) setConfirmClose(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('portfolio.confirmClose') || 'Confirm Close Position'}</DialogTitle>
            <DialogDescription>
              {confirmClose
                ? `${t('portfolio.close') || 'Close'} ${confirmClose.symbol} (${t('portfolio.position') || 'Size'}: ${Math.abs(confirmClose.size || 0)})`
                : ''}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmClose(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleClose}>
              {t('portfolio.confirmClose') || 'Confirm Close'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
})
