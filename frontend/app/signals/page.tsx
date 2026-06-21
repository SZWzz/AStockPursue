// frontend/app/signals/page.tsx — Trading signals list
'use client'

import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { EmptyState } from '@/components/ui/EmptyState'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

export default function SignalsPage() {
  const t = useTranslations()
  const { data, isLoading, error } = useSWR('/api/signals', fetcher)
  const signals = data?.data || data?.signals || data || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          Signals
        </h1>

        {isLoading ? (
          <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">
            {t('common.loading')}
          </div>
        ) : error ? (
          <div className="text-[13px] text-[var(--down)] text-center py-12">
            {t('common.error')}
            <button
              className="ml-2 underline text-[var(--foreground-secondary)]"
              onClick={() => window.location.reload()}
            >
              {t('common.retry')}
            </button>
          </div>
        ) : !signals.length ? (
          <EmptyState
            title={t('common.noData')}
            description="还没有交易信号，连接策略后查看生成的信号"
          />
        ) : null}
      </div>
    </SidebarLayout>
  )
}
