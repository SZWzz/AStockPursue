// frontend/app/trading/page.tsx — Real-time trading panel
import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { TradingContent } from '@/components/trading/TradingContent'
import { Skeleton } from '@/components/ui/Skeleton'

export default function TradingPage() {
  return (
    <SidebarLayout>
      <Suspense fallback={<Skeleton className="h-[600px] w-full" />}>
        <TradingContent />
      </Suspense>
    </SidebarLayout>
  )
}
