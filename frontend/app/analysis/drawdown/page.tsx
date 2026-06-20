// frontend/app/analysis/drawdown/page.tsx — Drawdown analysis
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useAnalysis } from '@/hooks'
import { DrawdownChart } from '@/components/financial/DrawdownChart'
import { Card } from '@/components/ui/card'

export default function DrawdownPage() {
  const t = useTranslations()
  const { trigger, data, isMutating, error } = useAnalysis()
  const [symbol, setSymbol] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const handleRun = () => {
    if (!symbol.trim()) return
    trigger({
      type: 'drawdown',
      params: {
        symbol: symbol.trim(),
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      },
    })
  }

  const result = data?.data || data

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('analysis.drawdown')}</h1>

        {/* Input card */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
          <div className="space-y-3">
            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                {t('trading.symbol')}
              </label>
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="000001.SZ"
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                  {t('backtest.startDate')}
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                  {t('backtest.endDate')}
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
            </div>
            <button
              onClick={handleRun}
              disabled={isMutating || !symbol.trim()}
              className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isMutating ? t('common.loading') : 'Run'}
            </button>
          </div>
        </Card>

        {/* Loading state */}
        {isMutating && (
          <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
            {t('common.loading')}
          </div>
        )}

        {/* Error state */}
        {error && !isMutating && (
          <div className="text-[13px] text-[var(--down)] text-center py-12">
            {t('common.error')}
            <button
              className="ml-2 underline text-[var(--foreground-secondary)]"
              onClick={handleRun}
            >
              {t('common.retry')}
            </button>
          </div>
        )}

        {/* Results */}
        {result && !isMutating && !error && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
            <DrawdownChart data={Array.isArray(result) ? result : result.data || []} />
          </Card>
        )}

        {/* Empty state */}
        {!data && !isMutating && !error && (
          <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
            {t('common.noData')}
          </div>
        )}
      </div>
    </SidebarLayout>
  )
}
