// frontend/app/analysis/correlation/page.tsx — Correlation analysis
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useAnalysis } from '@/hooks'
import { Skeleton } from '@/components/ui/Skeleton'
import dynamic from 'next/dynamic'
const CorrelationMatrix = dynamic(() => import('@/components/financial/CorrelationMatrix').then(mod => mod.CorrelationMatrix), { ssr: false, loading: () => <Skeleton className="h-[400px] w-full" /> })
import { DividerSection } from '@/components/financial/DividerSection'
import { Card } from '@/components/ui/card'

const LOOKBACK_OPTIONS = [
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
  { value: '180d', label: '180d' },
  { value: '1y', label: '1y' },
  { value: '2y', label: '2y' },
]

export default function CorrelationPage() {
  const t = useTranslations()
  const { trigger, data, isMutating, error } = useAnalysis()
  const [symbolsText, setSymbolsText] = useState('')
  const [lookback, setLookback] = useState('90d')

  const handleRun = () => {
    const symbols = symbolsText.split(',').map(s => s.trim()).filter(Boolean)
    if (!symbols.length) return
    trigger({ type: 'correlation', params: { symbols, lookback } })
  }

  const result = data?.data || data

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('analysis.correlation')}</h1>

        {/* Input card */}
        <Card className="p-[var(--card-padding)]">
          <div className="space-y-3">
            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                {t('trading.symbol')}
              </label>
              <textarea
                value={symbolsText}
                onChange={(e) => setSymbolsText(e.target.value)}
                placeholder="000001.SZ, 600036.SH, 000858.SZ"
                rows={3}
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 resize-none placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                {t('analysis.lookbackPeriod')}
              </label>
              <select
                value={lookback}
                onChange={(e) => setLookback(e.target.value)}
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 focus:outline-none focus:border-[var(--primary)]"
              >
                {LOOKBACK_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={handleRun}
              disabled={isMutating || !symbolsText.trim()}
              className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isMutating ? t('common.loading') : t('analysis.runStressTest')}
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
          <>
          <DividerSection title={t('analysis.correlation')} />
          <Card className="p-[var(--card-padding)]">
            <CorrelationMatrix
              symbols={result.symbols || []}
              matrix={result.matrix || []}
            />
          </Card>
          </>
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
