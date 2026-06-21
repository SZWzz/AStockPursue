// frontend/components/workflow/NodePanel.tsx
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useWorkflowStore } from '@/stores/workflowStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Node-type-specific config fields
interface NodeConfigField {
  key: string
  label: string
  type: 'input' | 'number' | 'select'
  options?: string[]
}

const NODE_CONFIG_MAP: Record<string, NodeConfigField[]> = {
  stockUniverse: [
    { key: 'market', label: 'Market', type: 'select', options: ['A-Share', 'HK', 'US', 'Crypto'] },
    { key: 'filter', label: 'Filter', type: 'input' },
    { key: 'limit', label: 'Limit', type: 'number' },
  ],
  dataLoader: [
    { key: 'source', label: 'Source', type: 'select', options: ['tushare', 'akshare', 'yfinance'] },
    { key: 'frequency', label: 'Frequency', type: 'select', options: ['daily', 'weekly', 'monthly'] },
    { key: 'lookback', label: 'Lookback Days', type: 'number' },
  ],
  alphaZoo: [
    { key: 'expression', label: 'Expression', type: 'input' },
    { key: 'window', label: 'Window', type: 'number' },
    { key: 'decay', label: 'Decay', type: 'number' },
  ],
  strategy: [
    { key: 'entryRule', label: 'Entry Rule', type: 'input' },
    { key: 'exitRule', label: 'Exit Rule', type: 'input' },
    { key: 'positionSize', label: 'Position Size', type: 'number' },
    { key: 'stopLoss', label: 'Stop Loss %', type: 'number' },
  ],
  backtest: [
    { key: 'startDate', label: 'Start Date', type: 'input' },
    { key: 'endDate', label: 'End Date', type: 'input' },
    { key: 'initialCapital', label: 'Initial Capital', type: 'number' },
    { key: 'frequency', label: 'Frequency', type: 'select', options: ['daily', 'minute'] },
  ],
  attribution: [
    { key: 'method', label: 'Method', type: 'select', options: ['Brinson', 'Factor-based', 'Shapley'] },
    { key: 'benchmark', label: 'Benchmark', type: 'input' },
  ],
  screener: [
    { key: 'conditions', label: 'Conditions', type: 'input' },
    { key: 'sortBy', label: 'Sort By', type: 'input' },
    { key: 'limit', label: 'Limit', type: 'number' },
  ],
  agent: [
    { key: 'model', label: 'Model', type: 'select', options: ['GPT-4', 'Claude', 'DeepSeek'] },
    { key: 'prompt', label: 'System Prompt', type: 'input' },
    { key: 'maxTokens', label: 'Max Tokens', type: 'number' },
  ],
}

export function NodePanel() {
  const t = useTranslations()
  const { selectedNode, setSelectedNode, runStatus, setRunStatus, setRunResult } = useWorkflowStore()
  const [editingFields, setEditingFields] = useState<Record<string, any>>({})

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
        <div className="text-[14px] text-[var(--foreground-secondary)] mb-3">{t('workflow.controls')}</div>
        <Button
          onClick={handleRun}
          disabled={runStatus === 'running'}
          className="w-full h-10"
        >
          {runStatus === 'running' ? t('workflow.running') : '▶ ' + t('workflow.runWorkflow')}
        </Button>
        {runStatus === 'done' && (
          <div className="mt-3 text-[12px] text-[var(--up)]">{t('workflow.executionComplete')}</div>
        )}
        {runStatus === 'error' && (
          <div className="mt-3 text-[12px] text-[var(--destructive)]">{t('workflow.executionFailed')}</div>
        )}
      </div>
    )
  }

  const nodeType = String(selectedNode.data?.type ?? '')
  const configFields = NODE_CONFIG_MAP[nodeType] || []

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4 max-h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[14px] font-semibold text-[var(--foreground)]">{t('workflow.nodeConfig')}</div>
        <button
          onClick={() => setSelectedNode(null)}
          className="text-[12px] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
        >
          ✕
        </button>
      </div>
      <div className="text-[12px] text-[var(--foreground-muted)] mb-1">{t('workflow.type')}</div>
      <div className="text-[13px] text-[var(--foreground)] mb-3">{nodeType}</div>
      <div className="text-[12px] text-[var(--foreground-muted)] mb-1">{t('workflow.label')}</div>
      <div className="text-[13px] text-[var(--foreground)] mb-4">{String(selectedNode.data?.label ?? '')}</div>

      {/* WE3: Type-specific configuration fields */}
      {configFields.length > 0 && (
        <div className="border-t border-[var(--border-subtle)] pt-3 space-y-3">
          <div className="text-[12px] font-semibold text-[var(--foreground-muted)] uppercase">
            Configuration
          </div>
          {configFields.map((field) => (
            <div key={field.key} className="space-y-1">
              <Label className="text-[11px] text-[var(--foreground-muted)]">{field.label}</Label>
              {field.type === 'select' && field.options ? (
                <Select
                  value={editingFields[field.key] || ''}
                  onValueChange={(v) => setEditingFields((prev) => ({ ...prev, [field.key]: v }))}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder={field.label} />
                  </SelectTrigger>
                  <SelectContent>
                    {field.options.map((opt) => (
                      <SelectItem key={opt} value={opt} className="text-xs">{opt}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  type={field.type === 'number' ? 'number' : 'text'}
                  value={editingFields[field.key] || ''}
                  onChange={(e) => setEditingFields((prev) => ({ ...prev, [field.key]: e.target.value }))}
                  className="h-8 text-xs"
                  placeholder={field.label}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
