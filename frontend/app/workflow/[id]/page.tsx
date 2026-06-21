// frontend/app/workflow/[id]/page.tsx
'use client'

import { use, useState } from 'react'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { WorkflowCanvas } from '@/components/workflow/WorkflowCanvas'
import { NodePalette } from '@/components/workflow/NodePalette'
import { NodePanel } from '@/components/workflow/NodePanel'
import { Button } from '@/components/ui/button'
import { useWorkflowStore } from '@/stores/workflowStore'
import { Save } from 'lucide-react'


export default function WorkflowEditorPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const t = useTranslations()
  const { id } = use(params)
  const { nodes, edges, loadWorkflow } = useWorkflowStore()
  const [saving, setSaving] = useState(false)

  // WE1: fetch workflow by ID on mount
  const { data, error, isLoading } = useSWR(id ? `/api/workflow/${id}` : null, {
    onSuccess: (data) => {
      const detail = data?.data || data
      if (detail?.nodes || detail?.dsl) {
        try {
          // If DSL is a JSON string, parse it
          let parsed = detail
          if (typeof detail.dsl === 'string' && detail.dsl.trim()) {
            parsed = JSON.parse(detail.dsl)
          }
          if (parsed?.nodes && parsed?.edges) {
            loadWorkflow(parsed.nodes, parsed.edges)
          } else if (detail?.nodes && detail?.edges) {
            loadWorkflow(detail.nodes, detail.edges)
          }
        } catch {
          // silently ignore parse errors
        }
      }
    },
  })

  // WE2: save workflow
  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(`/api/workflow/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes,
          edges,
          dsl: JSON.stringify({ nodes, edges }),
        }),
      })
      if (!res.ok) throw new Error('Save failed')
      toast.success(t('workflow.saveSuccess'))
    } catch {
      toast.error(t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  const workflowName = data?.data?.name || data?.name || `Workflow ${id}`

  return (
    <SidebarLayout>
      <div className="space-y-4">
        {/* Header with save button */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-semibold text-[var(--foreground)]">
            {isLoading ? t('common.loading') : workflowName}
          </h1>
          {/* WE2: Save button */}
          <Button onClick={handleSave} disabled={saving} size="sm">
            <Save className="w-4 h-4 mr-2" />
            {saving ? t('common.saving') || t('common.loading') : t('workflow.save')}
          </Button>
        </div>

        {error && (
          <p className="text-sm text-[var(--down)]">{t('common.error')}</p>
        )}

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
          <div className="w-[260px] shrink-0">
            <NodePanel />
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
