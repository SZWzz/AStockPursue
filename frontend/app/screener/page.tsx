// frontend/app/screener/page.tsx — Stock screener
'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { ScreenerGrid } from '@/components/financial/ScreenerGrid'
import { Card } from '@/components/ui/card'
import { useScreener } from '@/hooks'
import { useScreenerStore } from '@/stores'
import type { ScreenMode } from '@/stores'
import { cn } from '@/lib/utils'

interface ScreenerRow {
  symbol: string
  name?: string
  price: number
  change_pct: number
  volume: number
  score?: number
  rank?: number
}

const SORT_FIELDS = [
  { key: 'change_pct', labelKey: 'screener.change' },
  { key: 'volume', labelKey: 'screener.volume' },
  { key: 'price', labelKey: 'trading.price' },
]

// SR1: Extended filter field options
const FIELD_OPTIONS = [
  { value: 'price', labelKey: 'screener.price' },
  { value: 'change', labelKey: 'screener.change' },
  { value: 'volume', labelKey: 'screener.volume' },
  { value: 'pe', labelKey: 'screener.pe' },
  { value: 'market_cap', labelKey: 'screener.marketCap' },
  { value: 'dividend_yield', labelKey: 'screener.dividendYield' },
  { value: 'beta', labelKey: 'screener.beta' },
  { value: 'sector', labelKey: 'screener.sector' },
]

export default function ScreenerPage() {
  const t = useTranslations()
  const router = useRouter()
  const { trigger, data, isMutating, error } = useScreener()
  const {
    mode,
    setMode,
    conditions,
    addCondition,
    updateCondition,
    removeCondition,
    toggleLogic,
    clearConditions,
    sortField,
    sortDir,
    setSort,
    presets,
    savePreset,
    loadPreset,
    loadLocalPresets,
  } = useScreenerStore()

  const [presetName, setPresetName] = useState('')

  // SR5: Load presets from localStorage on mount
  useEffect(() => {
    loadLocalPresets()
  }, [loadLocalPresets])

  const handleRun = () => {
    const params: Record<string, any> = {}
    const logicGroups: string[] = []
    conditions.forEach((c) => {
      if (c.field && c.value) {
        params[`${c.field}_${c.operator}`] = Number(c.value)
        if (c.logic) logicGroups.push(c.logic)
      }
    })
    if (logicGroups.length > 0) params.logic = logicGroups
    if (sortField) params.sort_by = sortField
    if (sortDir) params.sort_order = sortDir
    if (mode !== 'filter') params.mode = mode
    trigger(params)
  }

  const handleReset = () => {
    clearConditions()
  }

  const handleSavePreset = () => {
    if (presetName.trim()) {
      savePreset(presetName.trim())
      setPresetName('')
    }
  }

  const results: ScreenerRow[] = data?.data || data?.results || data || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.screener')}</h1>

        {/* Filter form */}
        <Card className="p-[var(--card-padding)]">
          {/* Mode selector */}
          <div className="flex gap-2 mb-4">
            {(['filter', 'rank', 'score'] as ScreenMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  'px-4 py-1.5 rounded-[6px] text-[13px] font-medium transition-colors',
                  mode === m
                    ? 'bg-[var(--primary)] text-white'
                    : 'bg-[var(--surface-1)] text-[var(--foreground-secondary)] hover:text-[var(--foreground)]'
                )}
              >
                {t(`screener.${m}`)}
              </button>
            ))}
          </div>

          {/* Conditions */}
          {conditions.map((cond, i) => (
            <div key={i}>
              {/* SR2: AND/OR toggle between conditions */}
              {i > 0 && (
                <div className="flex items-center gap-2 mb-2">
                  <button
                    onClick={() => toggleLogic(i)}
                    className={cn(
                      'text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] border transition-colors',
                      cond.logic === 'OR'
                        ? 'bg-[var(--up)]/10 border-[var(--up)] text-[var(--up)]'
                        : 'bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)]'
                    )}
                    title={cond.logic === 'OR' ? t('screener.or') : t('screener.and')}
                  >
                    {cond.logic === 'OR' ? t('screener.or') : t('screener.and')}
                  </button>
                </div>
              )}

              <div className="flex gap-2 items-center mb-2">
                <select
                  value={cond.field}
                  onChange={(e) => updateCondition(i, { field: e.target.value })}
                  className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[13px] bg-white"
                >
                  {FIELD_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </select>
                <select
                  value={cond.operator}
                  onChange={(e) => updateCondition(i, { operator: e.target.value })}
                  className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[13px] bg-white"
                >
                  <option value=">">&gt;</option>
                  <option value="<">&lt;</option>
                  <option value=">=">&gt;=</option>
                  <option value="<=">&lt;=</option>
                </select>
                <input
                  value={cond.value}
                  onChange={(e) => updateCondition(i, { value: e.target.value })}
                  className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[13px] w-24 bg-white"
                />
                <button onClick={() => removeCondition(i)} className="text-[var(--destructive)] text-[12px]">
                  ✕
                </button>
              </div>
            </div>
          ))}
          <button onClick={addCondition} className="text-[12px] text-[var(--primary)] hover:underline mb-4">
            + {t('screener.addCondition')}
          </button>

          {/* Sort selector row */}
          <div className="flex items-center gap-3 mb-3">
            <span className="text-[12px] text-[var(--foreground-muted)]">{t('screener.sortBy')}</span>
            {SORT_FIELDS.map((field) => (
              <button
                key={field.key}
                onClick={() => {
                  if (sortField === field.key) {
                    setSort(field.key, sortDir === 'desc' ? 'asc' : 'desc')
                  } else {
                    setSort(field.key, 'desc')
                  }
                }}
                className={cn(
                  'text-[12px] font-medium px-2.5 py-0.5 rounded-[var(--radius-sm)] transition-colors border',
                  sortField === field.key
                    ? 'bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)]'
                    : 'border-[var(--border-default)] text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
                )}
              >
                {t(field.labelKey)}
                {sortField === field.key && (
                  <span className="ml-1">{sortDir === 'desc' ? '--' : '+'}</span>
                )}
              </button>
            ))}
          </div>

          {/* Preset save/load */}
          <div className="flex items-center gap-2 mb-3">
            <input
              type="text"
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder={t('screener.presetName')}
              className="h-8 rounded-[6px] border border-[var(--border)] px-2 text-[13px] w-40 bg-white"
            />
            <button onClick={handleSavePreset} className="text-[12px] text-[var(--primary)] hover:underline">
              {t('screener.savePreset')}
            </button>
            {presets.length > 0 && (
              <select
                onChange={(e) => {
                  if (e.target.value) loadPreset(e.target.value)
                }}
                className="h-8 rounded-[6px] border border-[var(--border)] px-2 text-[13px] bg-white"
                defaultValue=""
              >
                <option value="" disabled>
                  {t('screener.loadPreset')}
                </option>
                {presets.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleRun}
              disabled={isMutating}
              className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isMutating ? t('common.loading') : t('common.search')}
            </button>
            <button
              onClick={handleReset}
              className="text-[13px] text-[var(--foreground-secondary)] px-3 py-1.5 rounded-[var(--radius-sm)] hover:text-[var(--foreground)] transition-colors"
            >
              {t('common.reset')}
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
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={handleRun}
              >
                {t('common.retry')}
              </button>
            </div>
          </Card>
        )}

        {/* Results */}
        {results.length > 0 && !isMutating && !error && (
          <Card className="p-[var(--card-padding)]">
            <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">
              {t('screener.results')} ({results.length})
            </h2>
            <ScreenerGrid data={results} mode={mode} onRowClick={(symbol) => router.push('/trading?symbol=' + symbol)} />
          </Card>
        )}

        {/* Empty state */}
        {!data && !isMutating && !error && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
              {t('screener.emptyHint')}
            </div>
          </Card>
        )}

        {/* No results after search */}
        {data && !isMutating && !error && !results.length && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
              {t('common.noData')}
            </div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
