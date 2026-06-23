import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Skeleton } from '@/components/ui/Skeleton'
import { MarketplaceContent } from './MarketplaceContent'

function MarketplaceFallback() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="bg-[var(--surface-0)] border border-[var(--border)] rounded-[6px] p-4 space-y-3">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="grid grid-cols-3 gap-2">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function MarketplacePage() {
  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          策略模板市场
        </h1>
        <Suspense fallback={<MarketplaceFallback />}>
          <MarketplaceContent />
        </Suspense>
      </div>
    </SidebarLayout>
  )
}
