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

export default function DashboardPage() {
  const t = useTranslations()
  useWebSocket()
  const { data: posData } = usePositions()
  const { data: sysData } = useSystemStatus()

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('nav.dashboard')}
        </h1>

        <IndexTickerBar />

        {/* Hero KPI row — StatCallout for the main equity number */}
        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <StatCallout label={t('portfolio.totalEquity')} value="$100,000.00" change="+2.34%" direction="up" />
          <KpiCard label={t('portfolio.pnl')} value="+$2,340.00" direction="up" />
          <KpiCard label={t('portfolio.available')} value="$85,000.00" />
          <KpiCard label={t('portfolio.margin')} value="$15,000.00" change="15%" direction="neutral" />
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
