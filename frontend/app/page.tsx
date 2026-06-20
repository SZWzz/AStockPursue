// frontend/app/page.tsx
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { StatCallout } from '@/components/financial/StatCallout'
import { KpiCard } from '@/components/financial/KpiCard'
import { PositionTable } from '@/components/financial/PositionTable'
import { EquityChart } from '@/components/financial/EquityChart'
import { usePositions, useSystemStatus } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { IndexTickerBar } from '@/components/dashboard/IndexTickerBar'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export default function DashboardPage() {
  const t = useTranslations()
  useWebSocket()
  const { data: posData } = usePositions()
  const { data: sysData } = useSystemStatus()
  const { data: portfolio } = useSWR('/api/portfolio', fetcher)

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('nav.dashboard')}
        </h1>

        <IndexTickerBar />

        {/* Hero KPI row — StatCallout for the main equity number */}
        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <StatCallout
            label={t('portfolio.totalEquity')}
            value={portfolio?.total_value ? '$' + Number(portfolio.total_value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
            change={portfolio?.total_value && portfolio?.cash ? ((portfolio.total_value - portfolio.cash) / portfolio.cash * 100).toFixed(2) + '%' : '--'}
            direction={(portfolio?.total_value ?? 0) >= (portfolio?.cash ?? 0) ? 'up' : 'down'}
          />
          <KpiCard
            label={t('portfolio.pnl')}
            value={portfolio?.total_value && portfolio?.cash ? '$' + (portfolio.total_value - portfolio.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
            direction={((portfolio?.total_value ?? 0) - (portfolio?.cash ?? 0)) >= 0 ? 'up' : 'down'}
          />
          <KpiCard
            label={t('portfolio.available')}
            value={portfolio?.cash ? '$' + Number(portfolio.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
          />
          <KpiCard
            label={t('portfolio.margin')}
            value={portfolio?.total_value && portfolio?.cash ? '$' + (portfolio.total_value - portfolio.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
            change={portfolio?.total_value && portfolio?.cash ? ((portfolio.total_value - portfolio.cash) / portfolio.total_value * 100).toFixed(1) + '%' : '--'}
            direction="neutral"
          />
        </div>

        {/* Equity Chart + Positions */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('backtest.equityCurve')}</h2>
              <EquityChart data={[
                { time: '9:30', equity: 100000 },
                { time: '10:00', equity: 100500 },
                { time: '10:30', equity: 102340 }
              ]} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('nav.positions')}</h2>
              <PositionTable />
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
