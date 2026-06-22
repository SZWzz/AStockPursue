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
import { Save, Play, ChevronDown } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu'


export default function WorkflowEditorPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const t = useTranslations()
  const { id } = use(params)
  const { nodes, edges, loadWorkflow } = useWorkflowStore()
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState<{
    status: string
    error?: string
  } | null>(null)

  // WE1: fetch workflow by ID on mount
  const { data, error, isLoading } = useSWR(id ? `/api/workflow/${id}` : null, {
    onSuccess: (data) => {
      const detail = data?.data || data
      if (detail?.nodes || detail?.dsl) {
        try {
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

  // WE3: run workflow with mode
  const handleRun = async (mode: 'backtest' | 'paper' | 'live') => {
    setRunning(true)
    setRunResult(null)
    try {
      const res = await fetch(`/api/workflow/${id}/run?mode=${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          params: {
            nodes: JSON.stringify(nodes),
            edges: JSON.stringify(edges),
          },
        }),
      })
      const result = await res.json()
      if (!res.ok) {
        toast.error(result.error || `Run failed (${mode})`)
        setRunResult({ status: 'failed', error: result.error })
      } else {
        toast.success(`Workflow ${mode} completed: ${result.status}`)
        setRunResult({ status: result.status, error: result.error })
      }
    } catch {
      toast.error(t('common.error'))
      setRunResult({ status: 'failed', error: 'Network error' })
    } finally {
      setRunning(false)
    }
  }

  const workflowName = data?.data?.name || data?.name || `Workflow ${id}`

  return (
    <SidebarLayout>
      <div className="space-y-4">
        {/* Header with save + run buttons */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-semibold text-[var(--foreground)]">
            {isLoading ? t('common.loading') : workflowName}
          </h1>
          <div className="flex items-center gap-2">
            {/* WE3: Run dropdown button */}
            <DropdownMenu>
              <DropdownMenuTrigger disabled={running}>
                <Button disabled={running} size="sm">
                  {running ? (
                    <>
                      <span className="w-4 h-4 mr-2 animate-spin rounded-full border-2 border-current border-r-transparent" />
                      {t('common.running') || 'Running...'}
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      {t('workflow.run') || 'Run'}
                      <ChevronDown className="w-3 h-3 ml-1" />
                    </>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleRun('backtest')}>
                  <Play className="w-4 h-4 mr-2" />
                  Backtest
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleRun('paper')}>
                  <Play className="w-4 h-4 mr-2" />
                  Paper Trading
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleRun('live')}>
                  <Play className="w-4 h-4 mr-2" />
                  Live
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* WE2: Save button */}
            <Button onClick={handleSave} disabled={saving || running} size="sm">
              <Save className="w-4 h-4 mr-2" />
              {saving ? t('common.saving') || t('common.loading') : t('workflow.save')}
            </Button>
          </div>
        </div>

        {error && (
          <p className="text-sm text-[var(--down)]">{t('common.error')}</p>
        )}

        {/* Run result banner */}
        {runResult && (
          <div
            className={`px-4 py-3 rounded-md text-sm border ${
              runResult.status === 'completed'
                ? 'bg-green-50 border-green-200 text-green-800 dark:bg-green-950 dark:border-green-800 dark:text-green-200'
                : 'bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200'
            }`}
          >
            {runResult.status === 'completed'
              ? 'Workflow executed successfully.'
              : `Execution failed: ${runResult.error || 'Unknown error'}`}
          </div>
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
