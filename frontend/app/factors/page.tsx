// frontend/app/factors/page.tsx — Factor list
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'
import { useFactors } from '@/hooks'
import { cn } from '@/lib/utils'

interface Factor {
  id: string
  name: string
  formula: string
  ic?: number
  sharpe?: number
  status: string
}

const STATUS_COLORS: Record<string, string> = {
  production: 'bg-[var(--up)]/10 text-[var(--up)]',
  paper_trading: 'bg-[var(--primary)]/10 text-[var(--primary)]',
  validating: 'bg-[var(--warning)]/10 text-[var(--warning)]',
  discovered: 'bg-[var(--info)]/10 text-[var(--info)]',
  approved: 'bg-[var(--up)]/10 text-[var(--up)]',
  deprecated: 'bg-[var(--down)]/10 text-[var(--down)]',
  archived: 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]',
}

export default function FactorsPage() {
  const t = useTranslations()
  const router = useRouter()
  const [search, setSearch] = useState('')

  const { data, isLoading, error } = useFactors(search ? { search } : undefined)

  const factors: Factor[] = data?.data || data?.factors || data || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.factors')}</h1>

        {/* Search bar */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search factors by name or formula..."
            className="flex-1 bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
          />
        </div>

        {/* Content */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
          {isLoading ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
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
          ) : !factors.length ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                    <th className="text-left py-2.5 px-4 font-medium">Name</th>
                    <th className="text-left py-2.5 px-4 font-medium">Formula</th>
                    <th className="text-right py-2.5 px-4 font-medium">IC</th>
                    <th className="text-right py-2.5 px-4 font-medium">Sharpe</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('trading.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {factors.map((factor) => (
                    <tr
                      key={factor.id}
                      onClick={() => router.push(`/factors/${factor.id}`)}
                      className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-3)] cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-4 text-[13px] font-medium text-[var(--foreground)]">{factor.name}</td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-secondary)] max-w-[300px] truncate">
                        {factor.formula || '--'}
                      </td>
                      <td className={cn(
                        'py-2.5 px-4 text-[13px] font-mono tabular-nums text-right',
                        (factor.ic ?? 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'
                      )}>
                        {factor.ic !== undefined ? factor.ic.toFixed(4) : '--'}
                      </td>
                      <td className={cn(
                        'py-2.5 px-4 text-[13px] font-mono tabular-nums text-right',
                        (factor.sharpe ?? 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'
                      )}>
                        {factor.sharpe !== undefined ? factor.sharpe.toFixed(2) : '--'}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className={cn(
                          'inline-block text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]',
                          STATUS_COLORS[factor.status] || 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]'
                        )}>
                          {factor.status || '--'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </SidebarLayout>
  )
}
