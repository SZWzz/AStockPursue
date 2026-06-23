// frontend/app/market/page.tsx — Market overview
'use client'

import { useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { ScreenerGrid } from '@/components/financial/ScreenerGrid'
import { KpiCard } from '@/components/financial/KpiCard'
import { Card } from '@/components/ui/card'
import { cn, formatPercent } from '@/lib/utils'
import type { MarketRow } from '@/types'

/** Market mover — picks MarketRow fields used by the grid plus optional sector */
type MoverItem = Pick<MarketRow, 'symbol' | 'price' | 'change_pct' | 'volume'> & {
  name?: string
  sector?: string
}

interface OverviewData {
  total_stocks?: number
  up_count?: number
  down_count?: number
  up_pct?: number
  down_pct?: number
  total_volume?: number
  total_turnover?: number
}

export default function MarketOverviewPage() {
  const t = useTranslations()
  const router = useRouter()

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState<string>('all')

  const { data: moversData, isLoading: moversLoading, error: moversError } = useSWR(
    '/api/screener/movers',
    { refreshInterval: 10000 }
  )

  const { data: overviewData, isLoading: overviewLoading, error: overviewError } = useSWR(
    '/api/screener/overview',
    { refreshInterval: 30000 }
  )

  const movers: MoverItem[] = moversData?.data || moversData?.movers || moversData || []
  const overview: OverviewData = overviewData?.data || overviewData || {}

  // Derive sectors from movers if available
  const sectors = useMemo(() => {
    const set = new Set<string>()
    movers.forEach((m) => {
      if (m.sector) set.add(m.sector)
    })
    return Array.from(set).sort()
  }, [movers])

  // Filter movers by search query and sector
  const filteredMovers = useMemo(() => {
    return movers.filter((m) => {
      const matchesSearch =
        !searchQuery ||
        m.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (m.name && m.name.toLowerCase().includes(searchQuery.toLowerCase()))
      const matchesSector = selectedSector === 'all' || m.sector === selectedSector
      return matchesSearch && matchesSector
    })
  }, [movers, searchQuery, selectedSector])

  const handleRowClick = (symbol: string) => {
    router.push(`/market/${symbol}`)
  }

  const handleTrade = (symbol: string) => {
    router.push(`/trading?symbol=${symbol}`)
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      router.push(`/market/${searchQuery.trim()}`)
    }
  }

  const isLoading = moversLoading || overviewLoading
  const hasError = moversError || overviewError

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('market.overview')}</h1>

        {/* MK1: Symbol search bar */}
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder={t('market.searchSymbol')}
            className="w-full h-9 rounded-[6px] border border-[var(--border-default)] bg-[var(--surface-1)] px-3 text-[13px] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)] transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
            >
              ✕
            </button>
          )}
        </div>

        {/* Overview KPI cards */}
        {!overviewLoading && overview && (overview.total_stocks !== undefined || overview.up_count !== undefined) && (
          <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
            <KpiCard
              label={t('market.overview') + ' — ' + t('market.total')}
              value={overview.total_stocks !== undefined ? String(overview.total_stocks) : '--'}
            />
            <KpiCard
              label={t('market.up')}
              value={overview.up_count !== undefined ? String(overview.up_count) : '--'}
              direction="up"
            />
            <KpiCard
              label={t('market.down')}
              value={overview.down_count !== undefined ? String(overview.down_count) : '--'}
              direction="down"
            />
            <KpiCard
              label={t('market.upPct')}
              value={overview.up_pct !== undefined ? formatPercent(overview.up_pct / 100) : '--'}
              direction={overview.up_pct !== undefined && overview.up_pct >= 50 ? 'up' : 'down'}
            />
          </div>
        )}

        {/* MK2: Sector tabs/filter */}
        {sectors.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[12px] text-[var(--foreground-muted)] mr-1">{t('market.sector')}:</span>
            <button
              onClick={() => setSelectedSector('all')}
              className={cn(
                'text-[12px] font-medium px-2.5 py-0.5 rounded-[var(--radius-sm)] transition-colors border',
                selectedSector === 'all'
                  ? 'bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)]'
                  : 'border-[var(--border-default)] text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
              )}
            >
              {t('market.allSectors')}
            </button>
            {sectors.map((sector) => (
              <button
                key={sector}
                onClick={() => setSelectedSector(sector)}
                className={cn(
                  'text-[12px] font-medium px-2.5 py-0.5 rounded-[var(--radius-sm)] transition-colors border',
                  selectedSector === sector
                    ? 'bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)]'
                    : 'border-[var(--border-default)] text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
                )}
              >
                {sector}
              </button>
            ))}
          </div>
        )}

        {/* MK2: Sectors placeholder when no sector data */}
        {sectors.length === 0 && !isLoading && movers.length > 0 && (
          <Card className="p-[var(--card-padding)]">
            <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-1">{t('market.sectors')}</h2>
            <p className="text-[12px] text-[var(--foreground-muted)]">
              Sector breakdown not available for current data.
            </p>
          </Card>
        )}

        {/* Loading state */}
        {isLoading && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          </Card>
        )}

        {/* Error state */}
        {hasError && !isLoading && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => window.location.reload()}
              >
                {t('common.retry')}
              </button>
            </div>
          </Card>
        )}

        {/* Top Movers */}
        {!isLoading && !hasError && filteredMovers.length > 0 && (
          <Card className="p-[var(--card-padding)]">
            <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('market.topMovers')}</h2>
            <ScreenerGrid data={filteredMovers} onRowClick={handleRowClick} actionLabel={t('nav.trading')} onAction={handleTrade} />
          </Card>
        )}

        {/* Empty state */}
        {!isLoading && !hasError && !filteredMovers.length && (
          <Card className="p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
