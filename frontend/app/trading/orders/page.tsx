// frontend/app/trading/orders/page.tsx — Orders list with live updates
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { useOrders } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { formatPrice, cn } from '@/lib/utils'

/** Map order status to Badge variant for semantic coloring */
function badgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'filled':
      return 'default'
    case 'open':
      return 'secondary'
    case 'cancelled':
      return 'destructive'
    default:
      return 'outline'
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
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.orders')}</h1>

        <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
          {isLoading ? (
            <div className="text-[12px] text-[var(--foreground-muted)] p-4">{t('common.loading')}</div>
          ) : error ? (
            <div className="text-[12px] text-[var(--destructive)] p-4">{t('common.error')}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-[var(--border-subtle)] hover:bg-transparent">
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('trading.orderId')}</TableHead>
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('trading.symbol')}</TableHead>
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('trading.side')}</TableHead>
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('trading.price')}</TableHead>
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('trading.quantity')}</TableHead>
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8 text-right">{t('trading.filledQty')}</TableHead>
                  <TableHead className="text-[11px] text-[var(--foreground-muted)] h-8">{t('trading.status')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.length === 0 ? (
                  <TableRow className="border-[var(--border-subtle)]">
                    <TableCell colSpan={7} className="text-center text-[12px] text-[var(--foreground-muted)] h-16">
                      {t('common.noData')}
                    </TableCell>
                  </TableRow>
                ) : (
                  orders.map((order: any) => (
                    <TableRow key={order.id || order.order_id} className="border-[var(--border-subtle)] hover:bg-[var(--surface-3)]">
                      <TableCell className="text-[13px] font-mono py-1.5">
                        {(order.id || order.order_id || '-').slice(0, 12)}
                      </TableCell>
                      <TableCell className="text-[13px] font-mono font-medium py-1.5">{order.symbol}</TableCell>
                      <TableCell
                        className={cn(
                          'text-[13px] font-mono py-1.5',
                          order.side === 'buy' ? 'text-[var(--up)]' : 'text-[var(--down)]'
                        )}
                      >
                        {order.side === 'buy' ? t('trading.buy') : t('trading.sell')}
                      </TableCell>
                      <TableCell className="text-[13px] font-mono text-right py-1.5">{formatPrice(order.price)}</TableCell>
                      <TableCell className="text-[13px] font-mono text-right py-1.5">{order.quantity}</TableCell>
                      <TableCell className="text-[13px] font-mono text-right py-1.5">{order.filled_qty ?? order.filled ?? 0}</TableCell>
                      <TableCell className="py-1.5">
                        <Badge variant={badgeVariant(order.status)} className="text-[11px]">
                          {t(`trading.${order.status}` as any)}
                        </Badge>
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
