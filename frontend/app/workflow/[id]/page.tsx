// frontend/app/workflow/[id]/page.tsx — Workflow editor
'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CodeMirror } from '@/components/financial/CodeMirror'
import { LogViewer } from '@/components/financial/LogViewer'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface WorkflowDetail {
  id: string
  name: string
  description?: string
  dsl: string
  status: string
  node_count?: number
  last_run?: string | number
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-[var(--up)]/10 text-[var(--up)]',
  running: 'bg-[var(--up)]/10 text-[var(--up)]',
  idle: 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]',
  draft: 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]',
  error: 'bg-[var(--down)]/10 text-[var(--down)]',
  failed: 'bg-[var(--down)]/10 text-[var(--down)]',
}

export default function WorkflowEditorPage() {
  const t = useTranslations()
  const params = useParams()
  const id = params?.id as string

  const { data, isLoading, error, mutate } = useSWR(id ? `/api/workflow/${id}` : null, fetcher)

  const detail: WorkflowDetail | null = data?.data || data || null

  const [dsl, setDsl] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [runLogs, setRunLogs] = useState<string[]>([])
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (detail?.dsl !== undefined) {
      setDsl(detail.dsl)
    }
  }, [detail?.dsl])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await fetch(`/api/workflow/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dsl }),
      })
      mutate()
    } catch (e) {
      console.error('Failed to save workflow', e)
    } finally {
      setIsSaving(false)
    }
  }

  const handleRun = async () => {
    setIsRunning(true)
    setRunLogs([])
    try {
      const res = await fetch(`/api/workflow/${id}/run`, { method: 'POST' })
      const result = await res.json()
      const logs = result?.data?.logs || result?.logs || []
      setRunLogs(logs)
    } catch (e) {
      setRunLogs(['Error: Failed to execute workflow'])
      console.error('Failed to run workflow', e)
    } finally {
      setIsRunning(false)
      mutate()
    }
  }

  if (isLoading) {
    return (
      <SidebarLayout>
        <div className="flex items-center justify-center h-64 text-[13px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
      </SidebarLayout>
    )
  }

  if (error || !detail) {
    return (
      <SidebarLayout>
        <div className="flex flex-col items-center justify-center h-64 gap-2">
          <div className="text-[13px] text-[var(--down)]">{t('common.error')}</div>
          <button className="text-[13px] underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
            {t('common.retry')}
          </button>
        </div>
      </SidebarLayout>
    )
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{detail.name}</h1>
            {detail.description && (
              <p className="text-[12px] text-[var(--foreground-muted)] mt-0.5">{detail.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className={cn(
              'inline-block text-[11px] font-medium px-2.5 py-1 rounded-[var(--radius-sm)]',
              STATUS_COLORS[detail.status] || 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]'
            )}>
              {detail.status || '--'}
            </span>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="border border-[var(--border-default)] text-[var(--foreground-secondary)] text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:text-[var(--foreground)] hover:border-[var(--border-strong)] transition-colors disabled:opacity-50"
            >
              {isSaving ? t('common.loading') : t('common.save')}
            </button>
            <button
              onClick={handleRun}
              disabled={isRunning}
              className={cn(
                'text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] transition-opacity disabled:opacity-50 disabled:cursor-not-allowed',
                isRunning ? 'bg-[var(--foreground-muted)]' : 'bg-[var(--up)] hover:opacity-90'
              )}
            >
              {isRunning ? 'Running...' : 'Run'}
            </button>
          </div>
        </div>

        {/* DSL Editor */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
          <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">DSL</h2>
          <div className="border border-[var(--border-default)] rounded-[var(--radius-sm)] overflow-hidden" style={{ height: 400 }}>
            <CodeMirror
              value={dsl}
              readOnly={false}
              language="python"
              onChange={(value) => setDsl(value)}
            />
          </div>
        </Card>

        {/* Run Logs */}
        {runLogs.length > 0 && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
            <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">Execution Log</h2>
            <LogViewer logs={runLogs} />
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
