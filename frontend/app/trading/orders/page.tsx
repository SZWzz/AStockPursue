// frontend/app/trading/orders/page.tsx — Orders list with live updates, filters, cancel & pagination
'use client'

import { useState, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { StatusBadge } from '@/components/financial/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useOrders } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { formatPrice, cn } from '@/lib/utils'
import type { Order } from '@/types'
import { X, Search } from 'lucide-react'

interface DisplayOrder extends Order {
  order_id?: string
  filled_qty?: number
}

/** Map order status to StatusBadge variant */
function badgeStatus(status: string): 'filled' | 'cancelled' | 'pending' | 'error' | 'paused' {
  switch (status) {
    case 'filled':    return 'filled'
    case 'open':      return 'pending'
    case 'cancelled': return 'cancelled'
    case 'rejected':  return 'error'
    default:          return 'paused'
  }
}

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

export default function OrdersPage() {
  const t = useTranslations()
  useWebSocket()
  const { data, error, isLoading, mutate } = useOrders()

  // OR2: Filter states
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [symbolSearch, setSymbolSearch] = useState('')

  // OR3: Pagination states
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const [cancelling, setCancelling] = useState<string | null>(null)

  const orders = useMemo(() => {
    let list = data?.orders || []
    // Apply status filter
    if (statusFilter !== 'all') {
      list = list.filter((o: DisplayOrder) => (o.status || '').toLowerCase() === statusFilter)
    }
    // Apply symbol search
    if (symbolSearch) {
      const q = symbolSearch.toUpperCase()
      list = list.filter((o: DisplayOrder) => (o.symbol || '').toUpperCase().includes(q))
    }
    return list
  }, [data, statusFilter, symbolSearch])

  // Pagination calculations
  const totalCount = orders.length
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))
  const safePage = Math.min(page, totalPages)
  const paginatedOrders = orders.slice((safePage - 1) * pageSize, safePage * pageSize)

  // OR1: Cancel order
  const handleCancel = async (order: DisplayOrder) => {
    const id = order.id || order.order_id
    if (!id) return
    setCancelling(id)
    try {
      const res = await fetch(`/api/trading/orders/${id}`, { method: 'DELETE' })
      if (res.ok) {
        toast.success(t('trading.orderCancelled'))
        mutate()
      } else {
        toast.error(t('common.error'))
      }
    } catch {
      toast.error(t('common.error'))
    } finally {
      setCancelling(null)
    }
  }

  // Reset page when filters change
  const handleStatusChange = (v: string) => { setStatusFilter(v); setPage(1) }
  const handleSymbolSearch = (v: string) => { setSymbolSearch(v); setPage(1) }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.orders')}</h1>

        {/* OR2: Filters */}
        <div className="flex items-center gap-2">
          <Select value={statusFilter} onValueChange={(v) => handleStatusChange(v ?? 'all')}>
            <SelectTrigger className="w-[140px] h-8 text-[12px]">
              <SelectValue placeholder={t('trading.status')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('trading.allStatuses')}</SelectItem>
              <SelectItem value="open">{t('trading.open')}</SelectItem>
              <SelectItem value="filled">{t('trading.filled')}</SelectItem>
              <SelectItem value="cancelled">{t('trading.cancelled')}</SelectItem>
            </SelectContent>
          </Select>

          <div className="relative flex-1 max-w-[200px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--foreground-muted)]" />
            <input
              type="text"
              value={symbolSearch}
              onChange={(e) => handleSymbolSearch(e.target.value)}
              placeholder={t('trading.symbol')}
              className="w-full h-8 pl-8 pr-2 text-[12px] bg-white border border-[var(--border)] rounded-[6px] outline-none focus:border-[var(--primary)]"
            />
          </div>

          {symbolSearch && (
            <button
              onClick={() => handleSymbolSearch('')}
              className="text-[11px] text-[var(--foreground-muted)] hover:text-[var(--foreground)] flex items-center gap-1"
            >
              <X className="w-3 h-3" />
              {t('common.clear')}
            </button>
          )}
        </div>

        {/* Orders table */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] overflow-hidden">
          {isLoading ? (
            <SkeletonTable rows={5} cols={8} />
          ) : error ? (
            <div className="text-[12px] text-[var(--destructive)] p-12 text-center">{t('common.error')}</div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="h-8">{t('trading.orderId')}</TableHead>
                    <TableHead className="h-8">{t('trading.symbol')}</TableHead>
                    <TableHead className="h-8">{t('trading.side')}</TableHead>
                    <TableHead className="h-8 text-right">{t('trading.price')}</TableHead>
                    <TableHead className="h-8 text-right">{t('trading.quantity')}</TableHead>
                    <TableHead className="h-8 text-right">{t('trading.filledQty')}</TableHead>
                    <TableHead className="h-8">{t('trading.status')}</TableHead>
                    <TableHead className="h-8 text-right">{t('common.createOrder')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedOrders.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center text-[12px] text-[var(--foreground-muted)] h-16">
                        {t('common.noData')}
                      </TableCell>
                    </TableRow>
                  ) : (
                    paginatedOrders.map((order: DisplayOrder) => {
                      const id = order.id || order.order_id
                      const isOpen = (order.status || '').toLowerCase() === 'open'
                      return (
                        <TableRow key={id} className="hover:bg-[var(--surface-1)]">
                          <TableCell className="font-mono text-[12px]">
                            {id ? id.slice(0, 12) : '--'}
                          </TableCell>
                          <TableCell className="font-mono font-medium">{order.symbol}</TableCell>
                          <TableCell className={cn('font-mono', order.side === 'buy' ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                            {order.side === 'buy' ? t('trading.buy') : t('trading.sell')}
                          </TableCell>
                          <TableCell className="font-mono tabular-nums text-right">{formatPrice(order.price)}</TableCell>
                          <TableCell className="font-mono tabular-nums text-right">{order.quantity}</TableCell>
                          <TableCell className="font-mono tabular-nums text-right">{order.filled_qty ?? order.filled ?? 0}</TableCell>
                          <TableCell>
                            <StatusBadge status={badgeStatus(order.status)} label={t(`trading.${order.status}` as Parameters<typeof t>[0]) || order.status} />
                          </TableCell>
                          <TableCell className="text-right">
                            {isOpen && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleCancel(order)}
                                disabled={cancelling === id}
                                className="h-7 px-2 text-[11px] text-[var(--down)] hover:text-[var(--down)] hover:bg-[var(--down)]/10"
                              >
                                <X className="w-3.5 h-3.5 mr-1" />
                                {cancelling === id ? '...' : t('common.cancel')}
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>

              {/* OR3: Pagination footer */}
              {totalCount > 0 && (
                <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--border)]">
                  <div className="text-[11px] text-[var(--foreground-muted)]">
                    {t('trading.showing')} {(safePage - 1) * pageSize + 1}-{Math.min(safePage * pageSize, totalCount)} {t('trading.of')} {totalCount}
                  </div>

                  <div className="flex items-center gap-3">
                    <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1) }}>
                      <SelectTrigger className="w-[70px] h-7 text-[11px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PAGE_SIZE_OPTIONS.map(n => (
                          <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={safePage <= 1}
                        className="px-2 h-7 text-[11px] border border-[var(--border)] rounded-[4px] disabled:opacity-30 hover:bg-[var(--surface-1)]"
                      >
                        &lt;
                      </button>
                      <span className="text-[11px] text-[var(--foreground-muted)] px-1.5 tabular-nums">
                        {safePage} / {totalPages}
                      </span>
                      <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={safePage >= totalPages}
                        className="px-2 h-7 text-[11px] border border-[var(--border)] rounded-[4px] disabled:opacity-30 hover:bg-[var(--surface-1)]"
                      >
                        &gt;
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
