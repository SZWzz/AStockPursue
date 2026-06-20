// frontend/app/paper-trading/page.tsx — Paper trading list (Coinbase theme)
'use client'

import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { usePaperAccounts } from '@/hooks'
import { cn, formatPercent, formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { StatusBadge } from '@/components/financial/StatusBadge'

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
  const { data, isLoading, error } = usePaperAccounts()

  const accounts: PaperAccount[] = data?.accounts || data?.data || data || []

  const handleCreate = async () => {
    try {
      const res = await fetch('/api/papertrading', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: `Paper ${new Date().toLocaleDateString()}`, initial_capital: 100000 }),
      })
      if (res.ok) {
        const result = await res.json()
        const newAccount = result.data || result
        if (newAccount?.id) {
          router.push(`/paper-trading/${newAccount.id}`)
        }
      }
    } catch (e) {
      console.error('Failed to create paper trading account', e)
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.paperTrading')}</h1>
          <Button onClick={handleCreate}>
            {t('common.create')}
          </Button>
        </div>

        {/* Content */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] overflow-hidden">
          {isLoading ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          ) : error ? (
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button className="ml-2 underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
                {t('common.retry')}
              </button>
            </div>
          ) : !accounts.length ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t('trading.symbol')}</TableHead>
                  <TableHead>{t('backtest.strategy')}</TableHead>
                  <TableHead>{t('trading.status')}</TableHead>
                  <TableHead className="text-right">{t('portfolio.pnl')}</TableHead>
                  <TableHead className="text-right">{t('backtest.startDate')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acct) => (
                  <TableRow
                    key={acct.id}
                    onClick={() => router.push(`/paper-trading/${acct.id}`)}
                    className="cursor-pointer"
                  >
                    <TableCell className="font-medium">{acct.name}</TableCell>
                    <TableCell className="text-[var(--foreground-secondary)]">{acct.strategy || '--'}</TableCell>
                    <TableCell>
                      <StatusBadge status={(acct.status as any) || 'paused'} label={acct.status} />
                    </TableCell>
                    <TableCell className={cn('font-mono tabular-nums text-right', acct.pnl_pct !== undefined ? (acct.pnl_pct >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]') : 'text-[var(--foreground-secondary)]')}>
                      {acct.pnl_pct !== undefined ? formatPercent(acct.pnl_pct) : '--'}
                    </TableCell>
                    <TableCell className="font-mono text-[var(--foreground-muted)] text-right">
                      {formatDateTime(acct.created_at)}
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
