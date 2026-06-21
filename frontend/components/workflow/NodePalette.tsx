// frontend/components/workflow/NodePalette.tsx
'use client'

import { useTranslations } from 'next-intl'

const nodeTypes = [
  { type: 'stockUniverse', labelKey: 'Stock Universe', icon: '📊' },
  { type: 'dataLoader', labelKey: 'Data Loader', icon: '📥' },
  { type: 'alphaZoo', labelKey: 'Alpha Zoo', icon: '🧬' },
  { type: 'strategy', labelKey: 'Strategy', icon: '⚡' },
  { type: 'backtest', labelKey: 'Backtest', icon: '📈' },
  { type: 'attribution', labelKey: 'Attribution', icon: '🔍' },
  { type: 'screener', labelKey: 'Screener', icon: '🔎' },
  { type: 'agent', labelKey: 'AI Agent', icon: '🤖' },
]

export function NodePalette() {
  const t = useTranslations()

  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow-type', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-3">
      <div className="text-[12px] font-semibold text-[var(--foreground-muted)] mb-2 px-1">
        {t('workflow.nodeTypes')}
      </div>
      {nodeTypes.map((nt) => (
        <div
          key={nt.type}
          draggable
          onDragStart={(e) => onDragStart(e, nt.type)}
          className="flex items-center gap-2 px-3 py-2 text-[13px] text-[var(--foreground-secondary)] cursor-grab rounded-[4px] hover:bg-[var(--surface-1)] transition-colors"
        >
          <span className="text-[16px]">{nt.icon}</span>
          <span>{nt.labelKey}</span>
        </div>
      ))}
    </div>
  )
}
