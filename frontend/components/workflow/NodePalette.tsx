// frontend/components/workflow/NodePalette.tsx
'use client'

const nodeTypes = [
  { type: 'stockUniverse', label: 'Stock Universe', icon: '📊' },
  { type: 'dataLoader', label: 'Data Loader', icon: '📥' },
  { type: 'alphaZoo', label: 'Alpha Zoo', icon: '🧬' },
  { type: 'strategy', label: 'Strategy', icon: '⚡' },
  { type: 'backtest', label: 'Backtest', icon: '📈' },
  { type: 'attribution', label: 'Attribution', icon: '🔍' },
  { type: 'screener', label: 'Screener', icon: '🔎' },
  { type: 'agent', label: 'AI Agent', icon: '🤖' },
]

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow-type', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-3">
      <div className="text-[12px] font-semibold text-[var(--foreground-muted)] mb-2 px-1">
        NODE TYPES
      </div>
      {nodeTypes.map((nt) => (
        <div
          key={nt.type}
          draggable
          onDragStart={(e) => onDragStart(e, nt.type)}
          className="flex items-center gap-2 px-3 py-2 text-[13px] text-[var(--foreground-secondary)] cursor-grab rounded-[4px] hover:bg-[var(--surface-1)] transition-colors"
        >
          <span className="text-[16px]">{nt.icon}</span>
          <span>{nt.label}</span>
        </div>
      ))}
    </div>
  )
}
