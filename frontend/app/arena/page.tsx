import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Skeleton } from '@/components/ui/Skeleton'
import { ArenaContent } from './ArenaContent'

export default function ArenaPage() {
  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          回测竞技场
        </h1>
        <Suspense fallback={<ArenaFallback />}>
          <ArenaContent />
        </Suspense>
      </div>
    </SidebarLayout>
  )
}

function ArenaFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  )
}
