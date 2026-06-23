// frontend/app/market/page.tsx — Market overview
import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { MarketContent } from '@/components/market/MarketContent'
import { Skeleton } from '@/components/ui/Skeleton'

export default function MarketOverviewPage() {
  return (
    <SidebarLayout>
      <Suspense fallback={<Skeleton className="h-[600px] w-full" />}>
        <MarketContent />
      </Suspense>
    </SidebarLayout>
  )
}
