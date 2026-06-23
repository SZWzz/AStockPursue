// frontend/app/signals/page.tsx — Trading signals list
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn, formatDateTime } from '@/lib/utils'
import { Bell, BellOff, ArrowUpRight } from 'lucide-react'


interface Signal {
  id?: string
  signal_id?: string
  signal_type?: string
  type?: string
  symbol?: string
  direction?: string
  strength?: number
  confidence?: number
  timestamp?: string | number
  created_at?: string | number
  source?: string
  strategy?: string
  status?: string
}

function signalStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' | null | undefined {
  switch ((status || '').toLowerCase()) {
    case 'new':       return 'default'
    case 'acknowledged': return 'secondary'
    case 'acted':     return 'outline'
    case 'expired':   return 'destructive'
    default:          return 'secondary'
  }
}

export default function SignalsPage() {
  const t = useTranslations()
  const router = useRouter()
  const { data, isLoading, error, mutate } = useSWR('/api/signals')
  const signals: Signal[] = data?.data || data?.signals || data?.items || data || []

  const [actingId, setActingId] = useState<string | null>(null)

  const handleAcknowledge = async (signal: Signal) => {
    const id = signal.id || signal.signal_id
    if (!id) return
    setActingId(id)
    try {
      const res = await fetch(`/api/signals/${id}/ack`, { method: 'PUT' })
      if (res.ok) {
        toast.success(t('signals.acknowledge'))
        mutate()
      } else {
        toast.error(t('common.error'))
      }
    } catch {
      toast.error(t('common.error'))
    } finally {
      setActingId(null)
    }
  }

  const handleDismiss = async (signal: Signal) => {
    const id = signal.id || signal.signal_id
    if (!id) return
    setActingId(id)
    try {
      const res = await fetch(`/api/signals/${id}/dismiss`, { method: 'PUT' })
      if (res.ok) {
        toast.success(t('signals.dismiss'))
        mutate()
      } else {
        toast.error(t('common.error'))
      }
    } catch {
      toast.error(t('common.error'))
    } finally {
      setActingId(null)
    }
  }

  const handleCreateOrder = (signal: Signal) => {
    if (signal.symbol) {
      router.push(`/trading?symbol=${encodeURIComponent(signal.symbol)}&side=${signal.direction || 'buy'}`)
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('signals.title')}
        </h1>

        <div className="bg-white border border-[var(--border)] rounded-[6px] overflow-hidden">
          {isLoading ? (
            <SkeletonTable rows={5} cols={8} />
          ) : error ? (
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => window.location.reload()}
              >
                {t('common.retry')}
              </button>
            </div>
          ) : !signals.length ? (
            <EmptyState
              title={t('common.noData')}
              description={t('signals.noSignals')}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-8">{t('signals.type')}</TableHead>
                  <TableHead className="h-8">{t('trading.symbol')}</TableHead>
                  <TableHead className="h-8">{t('signals.direction')}</TableHead>
                  <TableHead className="h-8 text-right">{t('signals.strength')}</TableHead>
                  <TableHead className="h-8">{t('signals.timestamp')}</TableHead>
                  <TableHead className="h-8">{t('signals.source')}</TableHead>
                  <TableHead className="h-8">{t('signals.status')}</TableHead>
                  <TableHead className="h-8 text-right">{t('common.createOrder')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {signals.map((signal, idx) => {
                  const id = signal.id || signal.signal_id || `s-${idx}`
                  const status = (signal.status || 'new').toLowerCase()
                  const direction = (signal.direction || 'buy').toLowerCase()
                  const strength = signal.strength ?? signal.confidence ?? 0
                  const ts = signal.timestamp || signal.created_at

                  return (
                    <TableRow key={id} className="hover:bg-[var(--surface-1)]">
                      <TableCell className="font-medium">
                        {signal.signal_type || signal.type || '--'}
                      </TableCell>
                      <TableCell className="font-mono font-medium">{signal.symbol || '--'}</TableCell>
                      <TableCell>
                        <Badge
                          variant={direction === 'buy' ? 'default' : 'destructive'}
                          className="text-[11px] h-5"
                        >
                          {direction === 'buy' ? t('trading.buy') : t('trading.sell')}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono tabular-nums text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <div className="w-12 h-1.5 rounded-full bg-[var(--surface-3)] overflow-hidden">
                            <div
                              className={cn(
                                'h-full rounded-full transition-all',
                                strength >= 70 ? 'bg-[var(--down)]' :
                                strength >= 40 ? 'bg-[#F4B000]' :
                                'bg-[var(--up)]'
                              )}
                              style={{ width: `${Math.min(100, Math.max(0, strength))}%` }}
                            />
                          </div>
                          <span className="text-[12px] text-[var(--foreground-secondary)]">
                            {typeof strength === 'number' ? strength.toFixed(0) : '--'}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-[var(--foreground-muted)] text-[12px]">
                        {ts ? formatDateTime(ts) : '--'}
                      </TableCell>
                      <TableCell className="text-[var(--foreground-secondary)] text-[12px]">
                        {signal.source || signal.strategy || '--'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={signalStatusVariant(status)} className="text-[11px] h-5">
                          {t(`signals.${status}` as Parameters<typeof t>[0]) || status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {status === 'new' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-[11px]"
                                disabled={actingId === id}
                                onClick={() => handleAcknowledge(signal)}
                                title={t('signals.acknowledge')}
                              >
                                <Bell className="w-3.5 h-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-[11px] text-[var(--muted-foreground)]"
                                disabled={actingId === id}
                                onClick={() => handleDismiss(signal)}
                                title={t('signals.dismiss')}
                              >
                                <BellOff className="w-3.5 h-3.5" />
                              </Button>
                            </>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-[11px]"
                            onClick={() => handleCreateOrder(signal)}
                            title={t('signals.createOrder')}
                          >
                            <ArrowUpRight className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
