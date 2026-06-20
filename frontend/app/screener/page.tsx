// frontend/app/screener/page.tsx — Stock screener
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { ScreenerGrid } from '@/components/financial/ScreenerGrid'
import { Card } from '@/components/ui/card'
import { useScreener } from '@/hooks'
import { useScreenerStore } from '@/stores'
import { cn } from '@/lib/utils'

interface ScreenerRow {
  symbol: string
  name?: string
  price: number
  change_pct: number
  volume: number
}

const SORT_FIELDS = [
  { key: 'change_pct', labelKey: 'screener.change' },
  { key: 'volume', labelKey: 'screener.volume' },
  { key: 'price', labelKey: 'trading.price' },
]

export default function ScreenerPage() {
  const t = useTranslations()
  const { trigger, data, isMutating, error } = useScreener()
  const { conditions, setCondition, sortField, sortOrder, setSort, reset } = useScreenerStore()

  const [priceMin, setPriceMin] = useState('')
  const [priceMax, setPriceMax] = useState('')
  const [changeMin, setChangeMin] = useState('')
  const [volumeMin, setVolumeMin] = useState('')

  const handleRun = () => {
    const params: Record<string, any> = {}
    if (priceMin) params.price_min = Number(priceMin)
    if (priceMax) params.price_max = Number(priceMax)
    if (changeMin) params.change_pct_min = Number(changeMin)
    if (volumeMin) params.volume_min = Number(volumeMin)
    if (sortField) params.sort_by = sortField
    if (sortOrder) params.sort_order = sortOrder

    // Sync local inputs to store
    if (priceMin) setCondition('price_min', Number(priceMin))
    if (priceMax) setCondition('price_max', Number(priceMax))
    if (changeMin) setCondition('change_pct_min', Number(changeMin))
    if (volumeMin) setCondition('volume_min', Number(volumeMin))

    trigger(params)
  }

  const handleReset = () => {
    setPriceMin('')
    setPriceMax('')
    setChangeMin('')
    setVolumeMin('')
    reset()
  }

  const results: ScreenerRow[] = data?.data || data?.results || data || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.screener')}</h1>

        {/* Filter form */}
        <Card className="p-[var(--card-padding)]">
          <div className="grid grid-cols-4 gap-3 mb-3">
            <div>
              <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                Price Min
              </label>
              <input
                type="number"
                value={priceMin}
                onChange={(e) => setPriceMin(e.target.value)}
                placeholder="0"
                step="0.01"
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                Price Max
              </label>
              <input
                type="number"
                value={priceMax}
                onChange={(e) => setPriceMax(e.target.value)}
                placeholder="9999"
                step="0.01"
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                Change % Min
              </label>
              <input
                type="number"
                value={changeMin}
                onChange={(e) => setChangeMin(e.target.value)}
                placeholder="-10"
                step="0.1"
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                Volume Min
              </label>
              <input
                type="number"
                value={volumeMin}
                onChange={(e) => setVolumeMin(e.target.value)}
                placeholder="0"
                step="1"
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
              />
            </div>
          </div>

          {/* Sort selector row */}
          <div className="flex items-center gap-3 mb-3">
            <span className="text-[12px] text-[var(--foreground-muted)]">Sort by:</span>
            {SORT_FIELDS.map((field) => (
              <button
                key={field.key}
                onClick={() => {
                  if (sortField === field.key) {
                    setSort(field.key, sortOrder === 'desc' ? 'asc' : 'desc')
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
                  <span className="ml-1">{sortOrder === 'desc' ? '--' : '+'}</span>
                )}
              </button>
            ))}
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
              Reset
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
              Results ({results.length})
            </h2>
            <ScreenerGrid data={results} />
          </Card>
        )}

        {/* Empty state */}
        {!data && !isMutating && !error && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
              Set filters and click Search to find stocks
            </div>
          </Card>
        )}

        {/* No results after search */}
        {data && !isMutating && !error && !results.length && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
