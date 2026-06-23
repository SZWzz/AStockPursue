// frontend/app/paper-trading/page.tsx — Paper trading list (Coinbase theme)
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { usePaperAccounts } from '@/hooks'
import { cn, formatPercent, formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { StatusBadge } from '@/components/financial/StatusBadge'
import type { StatusVariant } from '@/components/financial/StatusBadge'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { EmptyState } from '@/components/ui/EmptyState'

interface PaperAccount {
  id: string
  name: string
  strategy: string
  status: string
  initial_capital?: number
  equity?: number
  pnl?: number
  pnl_pct?: number
  created_at: string | number
}

export default function PaperTradingPage() {
  const t = useTranslations()
  const router = useRouter()
  const { data, isLoading, error, mutate } = usePaperAccounts()

  const accounts: PaperAccount[] = data?.accounts || data?.data || data || []

  // PT2: Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [formName, setFormName] = useState('')
  const [formCapital, setFormCapital] = useState('100000')
  const [formStrategy, setFormStrategy] = useState('')
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    if (!formName.trim()) return
    setCreating(true)
    try {
      const res = await fetch('/api/papertrading', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName.trim(),
          initial_capital: parseFloat(formCapital) || 100000,
          strategy: formStrategy.trim() || undefined,
        }),
      })
      if (res.ok) {
        const result = await res.json()
        const newAccount = result.data || result
        setDialogOpen(false)
        setFormName('')
        setFormCapital('100000')
        setFormStrategy('')
        mutate()
        toast.success(t('common.create') + ' OK')
        if (newAccount?.id) {
          router.push(`/paper-trading/${newAccount.id}`)
        }
      } else {
        toast.error(t('common.error'))
      }
    } catch (e) {
      console.error('Failed to create paper trading account', e)
      toast.error(t('common.error'))
    } finally {
      setCreating(false)
    }
  }

  // PT3: Delete account
  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const res = await fetch(`/api/papertrading/${id}`, { method: 'DELETE' })
      if (res.ok) {
        toast.success(t('common.delete') + ' OK')
        mutate()
      } else {
        toast.error(t('common.error'))
      }
    } catch (err) {
      console.error('Failed to delete paper trading account', err)
      toast.error(t('common.error'))
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.paperTrading')}</h1>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger render={<Button>{t('common.create')}</Button>} />
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('nav.paperTrading')}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3 mt-2">
                <div>
                  <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                    {t('papertrading.name')}
                  </label>
                  <input
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder={t('papertrading.name')}
                    className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                    {t('papertrading.initialCapital')}
                  </label>
                  <input
                    type="number"
                    value={formCapital}
                    onChange={(e) => setFormCapital(e.target.value)}
                    placeholder="100000"
                    className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                    {t('papertrading.strategyName')}
                  </label>
                  <input
                    value={formStrategy}
                    onChange={(e) => setFormStrategy(e.target.value)}
                    placeholder={t('papertrading.strategyName')}
                    className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
                <Button onClick={handleCreate} disabled={creating || !formName.trim()} className="w-full">
                  {creating ? t('common.loading') : t('common.create')}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Content */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] overflow-hidden">
          {isLoading ? (
            <SkeletonTable rows={4} cols={5} />
          ) : error ? (
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button className="ml-2 underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
                {t('common.retry')}
              </button>
            </div>
          ) : !accounts.length ? (
            <EmptyState
              title={t('common.noData')}
              description={t('papertrading.emptyHint')}
              action={{ label: t('common.create'), href: '#' }}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t('backtest.strategy')}</TableHead>
                  <TableHead>{t('papertrading.name')}</TableHead>
                  <TableHead>{t('trading.status')}</TableHead>
                  <TableHead className="text-right">{t('portfolio.pnl')}</TableHead>
                  <TableHead className="text-right">{t('backtest.startDate')}</TableHead>
                  <TableHead className="w-[60px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acct) => (
                  <TableRow
                    key={acct.id}
                    onClick={() => router.push(`/paper-trading/${acct.id}`)}
                    className="cursor-pointer"
                  >
                    <TableCell className="font-medium">{acct.strategy || '--'}</TableCell>
                    <TableCell className="text-[var(--foreground-secondary)]">{acct.name}</TableCell>
                    <TableCell>
                      <StatusBadge status={(acct.status as StatusVariant) || 'paused'} label={acct.status} />
                    </TableCell>
                    <TableCell className={cn('font-mono tabular-nums text-right', acct.pnl_pct !== undefined ? (acct.pnl_pct >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]') : 'text-[var(--foreground-secondary)]')}>
                      {acct.pnl_pct !== undefined ? formatPercent(acct.pnl_pct) : '--'}
                    </TableCell>
                    <TableCell className="font-mono text-[var(--foreground-muted)] text-right">
                      {formatDateTime(acct.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={(e) => handleDelete(acct.id, e)}
                        className="text-[var(--foreground-muted)] hover:text-[var(--destructive)]"
                      >
                        {t('common.delete')}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </SidebarLayout>
  )
}
