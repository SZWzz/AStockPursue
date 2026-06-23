// frontend/app/page.tsx
import { Suspense } from 'react'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { DashboardContent, DashboardFallback } from '@/components/dashboard/DashboardContent'

export default function DashboardPage() {
  return (
    <SidebarLayout>
      <Suspense fallback={<DashboardFallback />}>
        <DashboardContent />
      </Suspense>
    </SidebarLayout>
  )
}
