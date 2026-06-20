// frontend/app/market/page.tsx — Market overview
'use client'

import useSWR from 'swr'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { ScreenerGrid } from '@/components/financial/ScreenerGrid'
import { KpiCard } from '@/components/financial/KpiCard'
import { Card } from '@/components/ui/card'
import { formatPercent } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface MoverItem {
  symbol: string
  name?: string
  price: number
  change_pct: number
  volume: number
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

  const { data: moversData, isLoading: moversLoading, error: moversError } = useSWR(
    '/api/screener/movers',
    fetcher,
    { refreshInterval: 10000 }
  )

  const { data: overviewData, isLoading: overviewLoading, error: overviewError } = useSWR(
    '/api/screener/overview',
    fetcher,
    { refreshInterval: 30000 }
  )

  const movers: MoverItem[] = moversData?.data || moversData?.movers || moversData || []
  const overview: OverviewData = overviewData?.data || overviewData || {}

  const isLoading = moversLoading || overviewLoading
  const hasError = moversError || overviewError

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('market.overview')}</h1>

        {/* Overview KPI cards */}
        {!overviewLoading && overview && (overview.total_stocks !== undefined || overview.up_count !== undefined) && (
          <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
            <KpiCard
              label={t('market.overview') + ' — ' + 'Total'}
              value={overview.total_stocks !== undefined ? String(overview.total_stocks) : '--'}
            />
            <KpiCard
              label="Up"
              value={overview.up_count !== undefined ? String(overview.up_count) : '--'}
              direction="up"
            />
            <KpiCard
              label="Down"
              value={overview.down_count !== undefined ? String(overview.down_count) : '--'}
              direction="down"
            />
            <KpiCard
              label="Up %"
              value={overview.up_pct !== undefined ? formatPercent(overview.up_pct / 100) : '--'}
              direction={overview.up_pct !== undefined && overview.up_pct >= 50 ? 'up' : 'down'}
            />
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          </Card>
        )}

        {/* Error state */}
        {hasError && !isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
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
        {!isLoading && !hasError && movers.length > 0 && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
            <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">Top Movers</h2>
            <ScreenerGrid data={movers} />
          </Card>
        )}

        {/* Empty state */}
        {!isLoading && !hasError && !movers.length && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
