// frontend/components/workflow/BaseNode.tsx
'use client'

import { Handle, Position, type NodeProps } from '@xyflow/react'

const nodeTypeLabels: Record<string, string> = {
  stockUniverse: 'Stock Universe',
  dataLoader: 'Data Loader',
  alphaZoo: 'Alpha Zoo',
  strategy: 'Strategy',
  backtest: 'Backtest',
  attribution: 'Attribution',
  screener: 'Screener',
  agent: 'AI Agent',
  notify: 'Notify',
}

export function BaseNode({ data, selected }: NodeProps) {
  const label: string = nodeTypeLabels[data.type as string] || (data.type as string) || 'Node'
  return (
    <div className={`
      px-4 py-3 rounded-[6px] border-2 min-w-[160px] text-[14px] font-medium shadow-sm
      ${selected
        ? 'border-[var(--primary)] bg-[var(--primary-muted)]'
        : 'border-[var(--border)] bg-white'
      }
    `}>
      <Handle type="target" position={Position.Left} className="!w-3 !h-3 !bg-[var(--border-strong)]" />
      <div className="text-[12px] text-[var(--foreground-muted)] mb-1">{label}</div>
      <div className="text-[var(--foreground)]">{data.label as string}</div>
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-[var(--primary)]" />
    </div>
  )
}
