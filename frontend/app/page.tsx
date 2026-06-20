// frontend/app/page.tsx
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { KpiCard } from '@/components/financial/KpiCard'
import { PositionTable } from '@/components/financial/PositionTable'
import { EquityChart } from '@/components/financial/EquityChart'
import { usePositions, useSystemStatus } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'

export default function DashboardPage() {
  const t = useTranslations()
  useWebSocket()
  const { data: posData } = usePositions()
  const { data: sysData } = useSystemStatus()

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.dashboard')}</h1>

        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <KpiCard label={t('portfolio.totalEquity')} value="$100,000.00" change="+2.34% today" direction="up" />
          <KpiCard label={t('portfolio.pnl')} value="+$2,340.00" direction="up" />
          <KpiCard label={t('portfolio.available')} value="$85,000.00" />
          <KpiCard label={t('portfolio.margin')} value="$15,000.00" change="15%" />
        </div>

        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('backtest.equityCurve')}</h2>
              <EquityChart data={[{ time: '9:30', equity: 100000 }, { time: '10:00', equity: 100500 }, { time: '10:30', equity: 102340 }]} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('nav.positions')}</h2>
              <PositionTable />
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
