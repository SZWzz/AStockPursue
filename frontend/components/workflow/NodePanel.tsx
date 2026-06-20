// frontend/components/workflow/NodePanel.tsx
'use client'

import { useWorkflowStore } from '@/stores/workflowStore'
import { Button } from '@/components/ui/button'

export function NodePanel() {
  const { selectedNode, setSelectedNode, runStatus, setRunStatus, setRunResult } = useWorkflowStore()

  const handleRun = async () => {
    setRunStatus('running')
    try {
      const res = await fetch('/api/workflow/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow_id: 'current' }),
      })
      if (!res.ok) throw new Error('Workflow execution failed')
      const data = await res.json()
      setRunResult(data)
      setRunStatus('done')
    } catch {
      setRunStatus('error')
    }
  }

  if (!selectedNode) {
    return (
      <div className="bg-white border border-[var(--border)] rounded-[6px] p-4">
        <div className="text-[14px] text-[var(--foreground-secondary)] mb-3">Workflow Controls</div>
        <Button
          onClick={handleRun}
          disabled={runStatus === 'running'}
          className="w-full h-10"
        >
          {runStatus === 'running' ? 'Running...' : '▶ Run Workflow'}
        </Button>
        {runStatus === 'done' && (
          <div className="mt-3 text-[12px] text-[var(--up)]">Execution complete</div>
        )}
        {runStatus === 'error' && (
          <div className="mt-3 text-[12px] text-[var(--destructive)]">Execution failed</div>
        )}
      </div>
    )
  }

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[14px] font-semibold text-[var(--foreground)]">Node Config</div>
        <button
          onClick={() => setSelectedNode(null)}
          className="text-[12px] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
        >
          ✕
        </button>
      </div>
      <div className="text-[12px] text-[var(--foreground-muted)] mb-1">Type</div>
      <div className="text-[13px] text-[var(--foreground)] mb-3">{String(selectedNode.data.type ?? '')}</div>
      <div className="text-[12px] text-[var(--foreground-muted)] mb-1">Label</div>
      <div className="text-[13px] text-[var(--foreground)]">{String(selectedNode.data.label ?? '')}</div>
    </div>
  )
}
