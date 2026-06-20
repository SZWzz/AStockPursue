// frontend/app/trading/positions/page.tsx — Dedicated positions management page
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { PositionTable } from '@/components/financial/PositionTable'
import { useWebSocket } from '@/hooks/useWebSocket'

export default function PositionsPage() {
  const t = useTranslations()
  useWebSocket()

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.positions')}</h1>

        <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
          <PositionTable />
        </div>
      </div>
    </SidebarLayout>
  )
}
