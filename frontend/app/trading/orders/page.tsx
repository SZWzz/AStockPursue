// frontend/app/trading/orders/page.tsx — Orders list with live updates (Coinbase theme)
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { StatusBadge } from '@/components/financial/StatusBadge'
import { useOrders } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { formatPrice, cn } from '@/lib/utils'

/** Map order status to StatusBadge variant */
function badgeStatus(status: string): 'filled' | 'cancelled' | 'pending' | 'error' | 'paused' {
  switch (status) {
    case 'filled':
      return 'filled'
    case 'open':
      return 'pending'
    case 'cancelled':
      return 'cancelled'
    case 'rejected':
      return 'error'
    default:
      return 'paused'
  }
}

export default function OrdersPage() {
  const t = useTranslations()
  useWebSocket()
  const { data, error, isLoading } = useOrders()

  const orders = data?.orders || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.orders')}</h1>

        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          {isLoading ? (
            <div className="text-[12px] text-[var(--foreground-muted)] p-4">{t('common.loading')}</div>
          ) : error ? (
            <div className="text-[12px] text-[var(--destructive)] p-4">{t('common.error')}</div>
          ) : (
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
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-[12px] text-[var(--foreground-muted)] h-16">
                      {t('common.noData')}
                    </TableCell>
                  </TableRow>
                ) : (
                  orders.map((order: any) => (
                    <TableRow key={order.id || order.order_id} className="hover:bg-[var(--surface-1)]">
                      <TableCell className="font-mono">
                        {(order.id || order.order_id || '-').slice(0, 12)}
                      </TableCell>
                      <TableCell className="font-mono font-medium">{order.symbol}</TableCell>
                      <TableCell
                        className={cn(
                          'font-mono',
                          order.side === 'buy' ? 'text-[var(--up)]' : 'text-[var(--down)]'
                        )}
                      >
                        {order.side === 'buy' ? t('trading.buy') : t('trading.sell')}
                      </TableCell>
                      <TableCell className="font-mono tabular-nums text-right">{formatPrice(order.price)}</TableCell>
                      <TableCell className="font-mono tabular-nums text-right">{order.quantity}</TableCell>
                      <TableCell className="font-mono tabular-nums text-right">{order.filled_qty ?? order.filled ?? 0}</TableCell>
                      <TableCell>
                        <StatusBadge status={badgeStatus(order.status)} label={t(`trading.${order.status}` as any)} />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
