// frontend/app/paper-trading/page.tsx — Paper trading list
'use client'

import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { usePaperAccounts } from '@/hooks'
import { cn, formatPercent, formatDateTime } from '@/lib/utils'
import { Card } from '@/components/ui/card'

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
          <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.paperTrading')}</h1>
          <button
            onClick={handleCreate}
            className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity"
          >
            {t('common.create')}
          </button>
        </div>

        {/* Content */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
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
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                  <th className="text-left py-2.5 px-4 font-medium">{t('trading.symbol')}</th>
                  <th className="text-left py-2.5 px-4 font-medium">{t('backtest.strategy')}</th>
                  <th className="text-left py-2.5 px-4 font-medium">{t('trading.status')}</th>
                  <th className="text-right py-2.5 px-4 font-medium">{t('portfolio.pnl')}</th>
                  <th className="text-right py-2.5 px-4 font-medium">{t('backtest.startDate')}</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((acct) => (
                  <tr
                    key={acct.id}
                    onClick={() => router.push(`/paper-trading/${acct.id}`)}
                    className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-3)] cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-4 text-[13px] font-medium text-[var(--foreground)]">{acct.name}</td>
                    <td className="py-2.5 px-4 text-[13px] text-[var(--foreground-secondary)]">{acct.strategy || '--'}</td>
                    <td className="py-2.5 px-4">
                      <span
                        className={cn(
                          'inline-block text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]',
                          acct.status === 'running'
                            ? 'bg-[var(--up)]/10 text-[var(--up)]'
                            : acct.status === 'stopped'
                            ? 'bg-[var(--down)]/10 text-[var(--down)]'
                            : 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]'
                        )}
                      >
                        {acct.status}
                      </span>
                    </td>
                    <td className={cn('py-2.5 px-4 text-[13px] font-mono tabular-nums text-right', acct.pnl_pct !== undefined ? (acct.pnl_pct >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]') : 'text-[var(--foreground-secondary)]')}>
                      {acct.pnl_pct !== undefined ? formatPercent(acct.pnl_pct) : '--'}
                    </td>
                    <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-muted)] text-right">
                      {formatDateTime(acct.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </SidebarLayout>
  )
}
