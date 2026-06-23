// frontend/app/paper-trading/[id]/page.tsx — Paper trading detail (Coinbase theme)
'use client'

import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { StatCallout } from '@/components/financial/StatCallout'
import { Skeleton } from '@/components/ui/Skeleton'
import dynamic from 'next/dynamic'
const EquityChart = dynamic(() => import('@/components/financial/EquityChart').then(mod => mod.EquityChart), { ssr: false, loading: () => <Skeleton className="h-[400px] w-full" /> })
import { TradeTimeline } from '@/components/financial/TradeTimeline'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useOrders } from '@/hooks'
import { formatPercent, formatDateTime } from '@/lib/utils'
import type { Order } from '@/types'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { toast } from 'sonner'

interface TradeItem {
  id: string
  symbol: string
  side: string
  price: number
  quantity: number
  pnl?: number
  time: number
}

interface PaperDetail {
  id: string
  name: string
  strategy: string
  status: string
  initial_capital: number
  equity: number
  pnl: number
  pnl_pct: number
  total_return: number
  max_drawdown: number
  total_trades: number
  equity_curve?: { time: string | number; equity: number }[]
  trades?: TradeItem[]
  created_at: string | number
}

export default function PaperTradingDetailPage() {
  const t = useTranslations()
  const params = useParams()
  const router = useRouter()
  const id = params?.id as string

  useWebSocket()

  const { data, isLoading, error, mutate } = useSWR(id ? `/api/papertrading/${id}` : null)

  // PD3: Order history
  const { data: ordersData } = useOrders()
  const orders: Order[] = ordersData?.orders || ordersData?.data || ordersData || []

  const detail: PaperDetail | null = data?.data || data || null

  const handleStart = async () => {
    try {
      await fetch(`/api/papertrading/${id}/start`, { method: 'POST' })
      mutate() // PD4: auto-refresh
    } catch {
      toast.error(t('common.error'))
    }
  }

  const handleStop = async () => {
    try {
      await fetch(`/api/papertrading/${id}/stop`, { method: 'POST' })
      mutate() // PD4: auto-refresh
    } catch {
      toast.error(t('common.error'))
    }
  }

  const handleGoLive = async () => {
    try {
      router.push(`/trading?deploy=${id}`)
    } catch (e) {
      toast.error(t('common.error'))
    }
  }

  if (isLoading) {
    return (
      <SidebarLayout>
        <div className="flex items-center justify-center h-64 text-[13px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
      </SidebarLayout>
    )
  }

  if (error || !detail) {
    return (
      <SidebarLayout>
        <div className="flex flex-col items-center justify-center h-64 gap-2">
          <div className="text-[13px] text-[var(--down)]">{t('common.error')}</div>
          <button className="text-[13px] underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
            {t('common.retry')}
          </button>
        </div>
      </SidebarLayout>
    )
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{detail.name}</h1>
            <p className="text-[12px] text-[var(--foreground-muted)] mt-0.5">
              {detail.strategy || '--'} &middot; {t('backtest.startDate')}: {formatDateTime(detail.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {detail.status !== 'running' && (
              <Button onClick={handleStart} variant="default">
                {t('common.start')}
              </Button>
            )}
            {detail.status === 'running' && (
              <Button onClick={handleStop} variant="outline">
                {t('common.stop')}
              </Button>
            )}
            <Button onClick={handleGoLive} variant="default" className="bg-[var(--up)] hover:bg-[var(--up)]/90">
              {t('papertrading.goLive')}
            </Button>
          </div>
        </div>

        {/* KPI Cards — StatCallout on white card */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-6">
          <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
            <StatCallout
              label={t('portfolio.totalEquity')}
              value={`$${(detail.equity ?? detail.initial_capital ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            />
            <StatCallout
              label={t('backtest.totalReturn')}
              value={detail.pnl_pct !== undefined ? formatPercent(detail.pnl_pct) : '--'}
            />
            <StatCallout
              label={t('backtest.maxDrawdown')}
              value={detail.max_drawdown !== undefined ? formatPercent(detail.max_drawdown) : '--'}
            />
            <StatCallout
              label={t('backtest.totalTrades')}
              value={detail.total_trades !== undefined ? String(detail.total_trades) : '0'}
            />
          </div>
        </div>

        {/* Chart + Timeline */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold mb-4 text-[var(--foreground)]">{t('backtest.equityCurve')}</h2>
              <EquityChart data={detail.equity_curve || []} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold mb-4 text-[var(--foreground)]">{t('backtest.tradeLog')}</h2>
              <TradeTimeline trades={detail.trades || []} />
            </div>
          </div>
        </div>

        {/* PD3: Order History */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <h2 className="text-[18px] font-semibold mb-4 text-[var(--foreground)]">{t('nav.orders')}</h2>
          {orders.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('trading.symbol')}</TableHead>
                  <TableHead>{t('trading.side')}</TableHead>
                  <TableHead className="text-right">{t('trading.price')}</TableHead>
                  <TableHead className="text-right">{t('trading.quantity')}</TableHead>
                  <TableHead>{t('trading.status')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map((o: Order, i: number) => (
                  <TableRow key={o.id || i}>
                    <TableCell className="font-medium">{o.symbol || '--'}</TableCell>
                    <TableCell>{o.side || '--'}</TableCell>
                    <TableCell className="font-mono tabular-nums text-right">{o.price != null ? o.price.toFixed(2) : '--'}</TableCell>
                    <TableCell className="font-mono tabular-nums text-right">{o.quantity ?? '--'}</TableCell>
                    <TableCell>{o.status || '--'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-6">{t('common.noData')}</div>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
