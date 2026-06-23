// frontend/app/backtest/page.tsx — Backtest list
import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { BacktestContent } from '@/components/backtest/BacktestContent'
import { Skeleton } from '@/components/ui/Skeleton'

export default function BacktestListPage() {
  return (
    <SidebarLayout>
      <Suspense fallback={<Skeleton className="h-[600px] w-full" />}>
        <BacktestContent />
      </Suspense>
    </SidebarLayout>
  )
}
