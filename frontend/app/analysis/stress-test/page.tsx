// frontend/app/analysis/stress-test/page.tsx — Stress test analysis
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { useAnalysis } from '@/hooks'
import { DividerSection } from '@/components/financial/DividerSection'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const SCENARIOS = [
  { value: 'market_crash', label: 'Market Crash -30%' },
  { value: 'rate_hike', label: 'Rate Hike +2%' },
  { value: 'vol_spike', label: 'Vol Spike +50%' },
  { value: 'custom', label: 'Custom' },
]

export default function StressTestPage() {
  const t = useTranslations()
  const { trigger, data, isMutating, error } = useAnalysis()
  const [scenario, setScenario] = useState('market_crash')
  const [customPct, setCustomPct] = useState('')

  const handleRun = () => {
    if (scenario === 'custom' && !customPct) return
    trigger({
      type: 'stressTest',
      params: {
        scenario,
        ...(scenario === 'custom' ? { custom_pct: parseFloat(customPct) } : {}),
      },
    })
  }

  const results: any[] = data?.data?.results || data?.results || data?.data || (data ? [data] : [])

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('analysis.stressTest')}</h1>

        {/* Input card */}
        <Card className="p-[var(--card-padding)]">
          <div className="space-y-3">
            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                Scenario
              </label>
              <select
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 focus:outline-none focus:border-[var(--primary)]"
              >
                {SCENARIOS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            {scenario === 'custom' && (
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                  Custom Impact (%)
                </label>
                <input
                  type="number"
                  value={customPct}
                  onChange={(e) => setCustomPct(e.target.value)}
                  placeholder="-20"
                  className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-2 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
            )}

            <button
              onClick={handleRun}
              disabled={isMutating || (scenario === 'custom' && !customPct)}
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

        {/* Results table */}
        {results.length > 0 && !isMutating && !error && (
          <>
          <DividerSection title={t('analysis.stressTest')} />
          <Card className="p-0 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                  <th className="text-left py-2.5 px-4 font-medium">Scenario</th>
                  <th className="text-right py-2.5 px-4 font-medium">Portfolio Impact</th>
                  <th className="text-right py-2.5 px-4 font-medium">VaR</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r: any, i: number) => (
                  <tr
                    key={i}
                    className="border-b border-[var(--border-subtle)] last:border-0"
                  >
                    <td className="py-2.5 px-4 text-[13px] font-medium text-[var(--foreground)]">
                      {r.scenario || r.name || SCENARIOS.find(s => s.value === scenario)?.label || '--'}
                    </td>
                    <td
                      className={cn(
                        'py-2.5 px-4 text-[13px] font-mono tabular-nums text-right',
                        r.impact !== undefined
                          ? r.impact >= 0
                            ? 'text-[var(--up)]'
                            : 'text-[var(--down)]'
                          : 'text-[var(--foreground-secondary)]'
                      )}
                    >
                      {r.impact !== undefined ? `${r.impact >= 0 ? '+' : ''}${r.impact}%` : '--'}
                    </td>
                    <td className="py-2.5 px-4 text-[13px] font-mono tabular-nums text-right text-[var(--foreground)]">
                      {r.var !== undefined ? `${r.var}%` : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
