// frontend/app/workflow/[id]/page.tsx
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { WorkflowCanvas } from '@/components/workflow/WorkflowCanvas'
import { NodePalette } from '@/components/workflow/NodePalette'
import { NodePanel } from '@/components/workflow/NodePanel'

export default function WorkflowEditorPage() {
  const t = useTranslations()

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('nav.workflow')}
        </h1>
        <div className="flex gap-4" style={{ height: 'calc(100vh - 180px)' }}>
          {/* Left: Node Palette */}
          <div className="w-[200px] shrink-0">
            <NodePalette />
          </div>
          {/* Center: Canvas */}
          <div className="flex-1 min-w-0">
            <WorkflowCanvas />
          </div>
          {/* Right: Node Panel */}
          <div className="w-[240px] shrink-0">
            <NodePanel />
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
