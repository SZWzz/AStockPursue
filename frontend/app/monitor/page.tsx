import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Skeleton } from '@/components/ui/Skeleton'
import { MonitorContent } from './MonitorContent'

export default function MonitorPage() {
  return (
    <SidebarLayout>
      <Suspense fallback={<MonitorFallback />}>
        <MonitorContent />
      </Suspense>
    </SidebarLayout>
  )
}

function MonitorFallback() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-10 w-36" />
        <Skeleton className="h-6 w-16" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-[var(--surface-0)] border border-[var(--border)] rounded-[6px] p-4 space-y-2">
            <Skeleton className="h-4 w-16 mx-auto" />
            <Skeleton className="h-8 w-20 mx-auto" />
            <Skeleton className="h-3 w-8 mx-auto" />
          </div>
        ))}
      </div>
      <Skeleton className="h-64 w-full rounded-[6px]" />
    </div>
  )
}
