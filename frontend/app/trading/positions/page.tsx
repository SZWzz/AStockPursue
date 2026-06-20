// frontend/app/trading/positions/page.tsx — Dedicated positions management page (Coinbase theme)
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
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.positions')}</h1>

        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <PositionTable />
        </div>
      </div>
    </SidebarLayout>
  )
}
