# Frontend 功能补全 — Phase 1+2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复旧版前端核心交互功能 — Workflow 可视化画布、Strategy Lab 代码 IDE、Dashboard 实时增强、Screener 多模式筛选

**Architecture:** 从旧版代码库（`C:/Users/shenz/Downloads/Compressed/astockpursue/frontend/`）迁移组件到新版 Next.js App Router，适配 Coinbase 白底主题，通过 Next.js BFF API Routes 连接 Go 后端

**Tech Stack:** Next.js 15, @xyflow/react, @monaco-editor/react, Recharts, Zustand, SWR, next-intl, Tailwind CSS 4

## Global Constraints

- 所有新代码在 `e:/coding/AStockPursue/frontend/` 下
- 旧版组件迁移时替换：`react-router-dom` → Next.js `Link`/`useRouter`，`useI18n()` → `useTranslations()`，`bg-[var(--surface-3)]` → `bg-white border border-[var(--border)]`
- 新组件使用 Coinbase 白底主题 token（`--foreground`、`--border`、`--primary` 等）
- 每 task 结束后 `npx next build` 通过
- Commit message: `feat(frontend): <description>`

---

## File Map

### 新建文件

```
frontend/
├── components/
│   ├── workflow/
│   │   ├── WorkflowCanvas.tsx      # @xyflow/react 画布
│   │   ├── NodePalette.tsx         # 可拖拽节点类型面板
│   │   ├── BaseNode.tsx            # 画布上自定义节点
│   │   └── NodePanel.tsx           # 节点配置侧栏
│   ├── strategy-lab/
│   │   ├── CodeEditor.tsx          # Monaco 编辑器封装
│   │   ├── ChartPanel.tsx          # Recharts 回测图表
│   │   └── BacktestPanel.tsx       # 回测参数 + 结果
│   └── dashboard/
│       └── IndexTickerBar.tsx      # 实时指数条
├── stores/
│   └── workflowStore.ts            # Zustand 工作流状态
└── app/
    ├── workflow/
    │   └── [id]/page.tsx           # 画布页（替换当前列表详情）
    └── strategy-lab/
        └── page.tsx                # Strategy Lab IDE
```

### 修改文件

```
frontend/
├── app/
│   ├── workflow/page.tsx           # 工作流列表 → 连接画布入口
│   ├── page.tsx                    # Dashboard → 真实数据 + 指数条
│   ├── screener/page.tsx           # 多模式筛选
│   └── trading/page.tsx            # PriceTicker 数据源切换
├── stores/
│   └── index.ts                    # 导出新 store
└── package.json                    # 加 @xyflow/react, @monaco-editor/react
```

---

### Task 1: 安装依赖 + 基础 scaffold

**Files:**
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `@xyflow/react`、`@monaco-editor/react` 可用

- [ ] **Step 1: Install dependencies**

```bash
cd e:/coding/AStockPursue/frontend
npm install @xyflow/react @monaco-editor/react
```

- [ ] **Step 2: Verify build**

```bash
npx next build 2>&1 | tail -5
```
Expected: Errors: 0 (new deps don't break anything)

- [ ] **Step 3: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add @xyflow/react and @monaco-editor/react dependencies"
```

---

### Task 2: Workflow Store（Zustand 状态管理）

**Files:**
- Create: `frontend/stores/workflowStore.ts`
- Modify: `frontend/stores/index.ts`

**Interfaces:**
- Consumes: `@xyflow/react` 类型（`Node`, `Edge`, `Connection`, `NodeChange`, `EdgeChange`）
- Produces: `useWorkflowStore` — Zustand store with `nodes`, `edges`, `selectedNode`, `runStatus`, `runResult`, `onNodesChange`, `onEdgesChange`, `onConnect`, `addNode`, `setSelectedNode`, `setRunStatus`, `setRunResult`

- [ ] **Step 1: Create workflowStore.ts**

```typescript
// frontend/stores/workflowStore.ts
import { create } from 'zustand'
import {
  type Node,
  type Edge,
  type Connection,
  type NodeChange,
  type EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
} from '@xyflow/react'

interface WorkflowState {
  nodes: Node[]
  edges: Edge[]
  selectedNode: Node | null
  runStatus: 'idle' | 'running' | 'done' | 'error'
  runResult: Record<string, unknown> | null
  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  addNode: (node: Node) => void
  setSelectedNode: (node: Node | null) => void
  setRunStatus: (status: WorkflowState['runStatus']) => void
  setRunResult: (result: Record<string, unknown> | null) => void
  loadWorkflow: (nodes: Node[], edges: Edge[]) => void
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  runStatus: 'idle',
  runResult: null,

  onNodesChange: (changes) => set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (connection) => set({ edges: addEdge(connection, get().edges) }),

  addNode: (node) => set({ nodes: [...get().nodes, node] }),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setRunStatus: (status) => set({ runStatus: status }),
  setRunResult: (result) => set({ runResult: result }),
  loadWorkflow: (nodes, edges) => set({ nodes, edges }),
}))
```

- [ ] **Step 2: Update stores/index.ts**

```typescript
// frontend/stores/index.ts
export { useUIStore } from './uiStore'
export { useThemeStore } from './themeStore'
export { useOrderFormStore } from './orderFormStore'
export { useScreenerStore } from './screenerStore'
export { useWSStore } from './wsStore'
export { useWorkflowStore } from './workflowStore'
```

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/stores/workflowStore.ts frontend/stores/index.ts
git commit -m "feat(frontend): add workflow Zustand store with xyflow node/edge state"
```

---

### Task 3: WorkflowCanvas + NodePalette（画布 + 节点面板）

**Files:**
- Create: `frontend/components/workflow/WorkflowCanvas.tsx`
- Create: `frontend/components/workflow/NodePalette.tsx`
- Create: `frontend/components/workflow/BaseNode.tsx`

**Interfaces:**
- Consumes: `useWorkflowStore` from Task 2
- Produces: `<WorkflowCanvas />` — ReactFlow wrapper; `<NodePalette />` — draggable node type list; `<BaseNode />` — custom node renderer

- [ ] **Step 1: Create BaseNode.tsx**

```tsx
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
  const label = nodeTypeLabels[data.type as string] || data.type || 'Node'
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
      <div className="text-[var(--foreground)]">{data.label}</div>
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-[var(--primary)]" />
    </div>
  )
}
```

- [ ] **Step 2: Create NodePalette.tsx**

```tsx
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
```

- [ ] **Step 3: Create WorkflowCanvas.tsx**

```tsx
// frontend/components/workflow/WorkflowCanvas.tsx
'use client'

import { useCallback, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useWorkflowStore } from '@/stores/workflowStore'
import { BaseNode } from './BaseNode'

const nodeTypes = { base: BaseNode }

export function WorkflowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, addNode } = useWorkflowStore()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const type = event.dataTransfer.getData('application/reactflow-type')
      if (!type || !reactFlowWrapper.current) return

      const bounds = reactFlowWrapper.current.getBoundingClientRect()
      const position = {
        x: event.clientX - bounds.left - 80,
        y: event.clientY - bounds.top - 20,
      }

      const newNode: Node = {
        id: `${type}-${Date.now()}`,
        type: 'base',
        position,
        data: { type, label: type },
      }
      addNode(newNode)
    },
    [addNode]
  )

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full" style={{ minHeight: 'calc(100vh - 180px)' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDragOver={onDragOver}
        onDrop={onDrop}
        nodeTypes={nodeTypes}
        fitView
        className="bg-[var(--surface-1)] rounded-[6px] border border-[var(--border)]"
      >
        <Background color="var(--border-subtle)" gap={20} />
        <Controls className="!bg-white !border !border-[var(--border)] !rounded-[6px]" />
        <MiniMap
          className="!bg-white !border !border-[var(--border)] !rounded-[6px]"
          maskColor="rgba(0,0,0,0.08)"
        />
      </ReactFlow>
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 5: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/components/workflow/
git commit -m "feat(frontend): add WorkflowCanvas, NodePalette, BaseNode components"
```

---

### Task 4: Workflow 画布页面（替换当前详情页）

**Files:**
- Modify: `frontend/app/workflow/[id]/page.tsx` — 改为画布模式
- Create: `frontend/components/workflow/NodePanel.tsx`

**Interfaces:**
- Consumes: `WorkflowCanvas`, `NodePalette`, `useWorkflowStore` from Tasks 2-3
- Produces: 可视化拖拽 DAG 编辑器页面

- [ ] **Step 1: Create NodePanel.tsx**

```tsx
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
      <div className="text-[13px] text-[var(--foreground)] mb-3">{selectedNode.data.type}</div>
      <div className="text-[12px] text-[var(--foreground-muted)] mb-1">Label</div>
      <div className="text-[13px] text-[var(--foreground)]">{selectedNode.data.label}</div>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite workflow/[id]/page.tsx**

```tsx
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
```

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/app/workflow/ frontend/components/workflow/NodePanel.tsx
git commit -m "feat(frontend): replace workflow detail page with visual DAG canvas editor"
```

---

### Task 5: Strategy Lab — CodeEditor + ChartPanel

**Files:**
- Create: `frontend/components/strategy-lab/CodeEditor.tsx`
- Create: `frontend/components/strategy-lab/ChartPanel.tsx`

**Interfaces:**
- Produces: `<CodeEditor />` — Monaco wrapper; `<ChartPanel />` — Recharts equity+drawdown chart

- [ ] **Step 1: Create CodeEditor.tsx**

```tsx
// frontend/components/strategy-lab/CodeEditor.tsx
'use client'

import dynamic from 'next/dynamic'

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

interface CodeEditorProps {
  code: string
  onChange: (value: string | undefined) => void
  language?: string
  height?: string
}

export function CodeEditor({ code, onChange, language = 'python', height = '400px' }: CodeEditorProps) {
  return (
    <div className="border border-[var(--border)] rounded-[6px] overflow-hidden">
      <MonacoEditor
        height={height}
        language={language}
        value={code}
        onChange={onChange}
        theme="vs"
        options={{
          fontSize: 13,
          fontFamily: 'var(--font-mono)',
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          lineNumbers: 'on',
          renderLineHighlight: 'line',
          tabSize: 4,
        }}
      />
    </div>
  )
}
```

- [ ] **Step 2: Create ChartPanel.tsx**

```tsx
// frontend/components/strategy-lab/ChartPanel.tsx
'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface ChartPanelProps {
  equityData: { time: string; equity: number }[]
  title?: string
}

export function ChartPanel({ equityData, title = 'Equity Curve' }: ChartPanelProps) {
  if (!equityData.length) {
    return (
      <div className="bg-white border border-[var(--border)] rounded-[6px] p-6 flex items-center justify-center h-[300px]">
        <span className="text-[14px] text-[var(--foreground-muted)]">Run a backtest to see results</span>
      </div>
    )
  }

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4">
      <h3 className="text-[14px] font-semibold text-[var(--foreground)] mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={equityData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--foreground-muted)' }} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--foreground-muted)' }} />
          <Tooltip
            contentStyle={{
              background: '#fff',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              fontSize: '13px',
            }}
          />
          <Line type="monotone" dataKey="equity" stroke="var(--primary)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/components/strategy-lab/
git commit -m "feat(frontend): add CodeEditor (Monaco) and ChartPanel (Recharts) for Strategy Lab"
```

---

### Task 6: Strategy Lab 页面

**Files:**
- Create: `frontend/app/strategy-lab/page.tsx`
- Create: `frontend/components/strategy-lab/BacktestPanel.tsx`

- [ ] **Step 1: Create BacktestPanel.tsx**

```tsx
// frontend/components/strategy-lab/BacktestPanel.tsx
'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface BacktestPanelProps {
  onRun: (config: { symbol: string; startDate: string; endDate: string }) => void
  running: boolean
  result: { totalReturn?: number; sharpeRatio?: number; maxDrawdown?: number } | null
}

export function BacktestPanel({ onRun, running, result }: BacktestPanelProps) {
  const [symbol, setSymbol] = useState('000001.SZ')
  const [startDate, setStartDate] = useState('2026-01-01')
  const [endDate, setEndDate] = useState('2026-06-20')

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4 space-y-3">
      <h3 className="text-[14px] font-semibold text-[var(--foreground)]">Backtest Config</h3>
      <div>
        <label className="text-[12px] text-[var(--foreground-muted)]">Symbol</label>
        <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="h-10 mt-1" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[12px] text-[var(--foreground-muted)]">Start</label>
          <Input value={startDate} onChange={(e) => setStartDate(e.target.value)} className="h-10 mt-1" />
        </div>
        <div>
          <label className="text-[12px] text-[var(--foreground-muted)]">End</label>
          <Input value={endDate} onChange={(e) => setEndDate(e.target.value)} className="h-10 mt-1" />
        </div>
      </div>
      <Button
        onClick={() => onRun({ symbol, startDate, endDate })}
        disabled={running}
        className="w-full h-10"
      >
        {running ? 'Running...' : '▶ Run Backtest'}
      </Button>
      {result && (
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[var(--border-subtle)]">
          <div>
            <div className="text-[11px] text-[var(--foreground-muted)]">Return</div>
            <div className={`text-[18px] font-mono font-semibold ${(result.totalReturn || 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'}`}>
              {((result.totalReturn || 0) * 100).toFixed(2)}%
            </div>
          </div>
          <div>
            <div className="text-[11px] text-[var(--foreground-muted)]">Sharpe</div>
            <div className="text-[18px] font-mono font-semibold text-[var(--foreground)]">
              {(result.sharpeRatio || 0).toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-[var(--foreground-muted)]">Max DD</div>
            <div className="text-[18px] font-mono font-semibold text-[var(--down)]">
              {((result.maxDrawdown || 0) * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create strategy-lab page**

```tsx
// frontend/app/strategy-lab/page.tsx
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CodeEditor } from '@/components/strategy-lab/CodeEditor'
import { ChartPanel } from '@/components/strategy-lab/ChartPanel'
import { BacktestPanel } from '@/components/strategy-lab/BacktestPanel'

const DEFAULT_CODE = `# Strategy: Momentum Breakout
# Symbol: {symbol}  |  Period: {start} → {end}

def generate(df, params):
    fast = params.get('fast', 5)
    slow = params.get('slow', 20)
    df['ma_fast'] = df['close'].rolling(fast).mean()
    df['ma_slow'] = df['close'].rolling(slow).mean()
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
    return df
`

export default function StrategyLabPage() {
  const t = useTranslations()
  const [code, setCode] = useState(DEFAULT_CODE)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, number> | null>(null)
  const [equityData, setEquityData] = useState<{ time: string; equity: number }[]>([])

  const handleRun = async (config: { symbol: string; startDate: string; endDate: string }) => {
    setRunning(true)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: 'StrategyLab',
          symbol: config.symbol,
          start_date: config.startDate,
          end_date: config.endDate,
          frequency: 'daily',
          initial_capital: 100000,
        }),
      })
      if (!res.ok) throw new Error('Backtest failed')
      const data = await res.json()
      setResult({
        totalReturn: data.total_return || 0,
        sharpeRatio: data.sharpe_ratio || 0,
        maxDrawdown: data.max_drawdown || 0,
      })
      if (data.equity_curve) {
        setEquityData(data.equity_curve.map((e: { time: string; equity: number }) => ({
          time: e.time?.slice(0, 10) || '',
          equity: e.equity,
        })))
      }
    } catch {
      setResult(null)
    } finally {
      setRunning(false)
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          Strategy Lab
        </h1>
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8 space-y-4">
            <CodeEditor code={code} onChange={setCode} height="400px" />
            <ChartPanel equityData={equityData} />
          </div>
          <div className="col-span-4">
            <BacktestPanel onRun={handleRun} running={running} result={result} />
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
```

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/app/strategy-lab/ frontend/components/strategy-lab/BacktestPanel.tsx
git commit -m "feat(frontend): add Strategy Lab IDE with code editor + backtest + chart"
```

---

### Task 7: Dashboard 增强 — 实时数据连接

**Files:**
- Modify: `frontend/app/page.tsx` — 连接 WebSocket + API 数据
- Create: `frontend/components/dashboard/IndexTickerBar.tsx`

- [ ] **Step 1: Create IndexTickerBar.tsx**

```tsx
// frontend/components/dashboard/IndexTickerBar.tsx
'use client'

import { useEffect, useState } from 'react'
import { wsClient } from '@/lib/ws'
import { cn } from '@/lib/utils'

interface TickerData {
  symbol: string
  price: number
  change: number
}

export function IndexTickerBar() {
  const [tickers, setTickers] = useState<Record<string, TickerData>>({
    '000001.SZ': { symbol: '000001.SZ', price: 0, change: 0 },
    '600519.SH': { symbol: '600519.SH', price: 0, change: 0 },
    '000300.SH': { symbol: '000300.SH', price: 0, change: 0 },
  })

  useEffect(() => {
    const unsub = wsClient.on('ticker', (_channel, data) => {
      if (data?.symbol && tickers[data.symbol]) {
        setTickers((prev) => ({
          ...prev,
          [data.symbol]: { symbol: data.symbol, price: data.price, change: data.change },
        }))
      }
    })
    return unsub
  }, [])

  return (
    <div className="flex gap-4 bg-white border border-[var(--border)] rounded-[6px] px-4 py-2">
      {Object.values(tickers).map((t) => (
        <div key={t.symbol} className="flex items-center gap-3">
          <span className="text-[12px] font-mono text-[var(--foreground)]">{t.symbol}</span>
          <span className="text-[14px] font-mono tabular-nums text-[var(--foreground)]">
            {t.price ? t.price.toFixed(2) : '--'}
          </span>
          <span className={cn(
            'text-[12px] font-mono',
            t.change > 0 ? 'text-[var(--up)]' : t.change < 0 ? 'text-[var(--down)]' : 'text-[var(--foreground-muted)]'
          )}>
            {t.change ? `${t.change > 0 ? '+' : ''}${(t.change * 100).toFixed(2)}%` : '--'}
          </span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Update Dashboard to use WebSocket data**

Add IndexTickerBar and WebSocket connection to `frontend/app/page.tsx`. Replace hardcoded KPI values with SWR fetches where available, keep sample data as fallback:

Modify the Dashboard page to:
1. Import and use `useWebSocket` + `IndexTickerBar`
2. Place IndexTickerBar above the KPI row
3. Wrap KpiCard values in SWR with fallback to samples

(For brevity the full page code is in the spec; key changes: add `<IndexTickerBar />` after `<h1>`, add `useWebSocket()` call)

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/app/page.tsx frontend/components/dashboard/
git commit -m "feat(frontend): add real-time IndexTickerBar + WebSocket data to Dashboard"
```

---

### Task 8: Screener 增强 — 多模式筛选

**Files:**
- Modify: `frontend/app/screener/page.tsx`
- Modify: `frontend/stores/screenerStore.ts`

- [ ] **Step 1: Update screenerStore — add modes and presets**

```typescript
// frontend/stores/screenerStore.ts
import { create } from 'zustand'

export type ScreenMode = 'filter' | 'rank' | 'score'

interface ScreenerState {
  mode: ScreenMode
  conditions: Array<{ field: string; operator: string; value: string }>
  sortField: string
  sortDir: 'asc' | 'desc'
  presets: Array<{ name: string; config: ScreenerState }>
  setMode: (mode: ScreenMode) => void
  addCondition: () => void
  updateCondition: (index: number, field: Partial<ScreenerState['conditions'][0]>) => void
  removeCondition: (index: number) => void
  setSort: (field: string, dir: 'asc' | 'desc') => void
  savePreset: (name: string) => void
  loadPreset: (name: string) => void
}

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  mode: 'filter',
  conditions: [],
  sortField: 'change',
  sortDir: 'desc',
  presets: [],
  setMode: (mode) => set({ mode }),
  addCondition: () => set({ conditions: [...get().conditions, { field: 'price', operator: '>', value: '0' }] }),
  updateCondition: (index, field) => {
    const conditions = [...get().conditions]
    conditions[index] = { ...conditions[index], ...field }
    set({ conditions })
  },
  removeCondition: (index) => set({ conditions: get().conditions.filter((_, i) => i !== index) }),
  setSort: (field, dir) => set({ sortField: field, sortDir: dir }),
  savePreset: (name) => set({ presets: [...get().presets, { name, config: JSON.parse(JSON.stringify(get())) }] }),
  loadPreset: (name) => {
    const preset = get().presets.find((p) => p.name === name)
    if (preset) {
      const { presets, ...config } = preset.config
      set({ ...config, presets: get().presets })
    }
  },
}))
```

- [ ] **Step 2: Update Screener page with mode tabs and condition builder**

Add mode selector (Filter / Rank / Score), condition rows with field/operator/value inputs, and preset save/load. Key UI additions to `frontend/app/screener/page.tsx`:

```tsx
{/* Mode selector */}
<div className="flex gap-2 mb-4">
  {(['filter', 'rank', 'score'] as ScreenMode[]).map((m) => (
    <button
      key={m}
      onClick={() => setMode(m)}
      className={`px-4 py-1.5 rounded-[6px] text-[13px] font-medium transition-colors ${
        mode === m
          ? 'bg-[var(--primary)] text-white'
          : 'bg-[var(--surface-1)] text-[var(--foreground-secondary)] hover:text-[var(--foreground)]'
      }`}
    >
      {m === 'filter' ? 'Filter' : m === 'rank' ? 'Rank' : 'Score'}
    </button>
  ))}
</div>

{/* Conditions */}
{conditions.map((cond, i) => (
  <div key={i} className="flex gap-2 items-center mb-2">
    <select value={cond.field} onChange={(e) => updateCondition(i, { field: e.target.value })}
      className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[13px] bg-white">
      <option value="price">Price</option>
      <option value="change">Change %</option>
      <option value="volume">Volume</option>
      <option value="pe">P/E</option>
    </select>
    <select value={cond.operator} onChange={(e) => updateCondition(i, { operator: e.target.value })}
      className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[13px] bg-white">
      <option value=">">&gt;</option>
      <option value="<">&lt;</option>
      <option value=">=">&gt;=</option>
      <option value="<=">&lt;=</option>
    </select>
    <input value={cond.value} onChange={(e) => updateCondition(i, { value: e.target.value })}
      className="h-9 rounded-[6px] border border-[var(--border)] px-2 text-[13px] w-24 bg-white" />
    <button onClick={() => removeCondition(i)}
      className="text-[var(--destructive)] text-[12px]">✕</button>
  </div>
))}
<button onClick={addCondition}
  className="text-[12px] text-[var(--primary)] hover:underline mb-4">+ Add Condition</button>
```

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/app/screener/ frontend/stores/screenerStore.ts
git commit -m "feat(frontend): add multi-mode screener with condition builder and presets"
```

---

### Task 9: 导航注册 + i18n 补齐

**Files:**
- Modify: `frontend/lib/navigation.ts` — 添加 Strategy Lab 到侧栏
- Modify: `frontend/messages/en.json` — 新 key
- Modify: `frontend/messages/zh.json` — 新 key

- [ ] **Step 1: Add Strategy Lab to navigation**

```typescript
// In frontend/lib/navigation.ts, add to RESEARCH group:
{
  key: 'strategy-lab',
  label: 'strategyLab',
  href: '/strategy-lab',
  icon: Code2, // from lucide-react
}
```

- [ ] **Step 2: Add i18n keys**

```json
// en.json
"nav.strategyLab": "Strategy Lab",
"nav.workflow": "Workflow",
"screener.filter": "Filter",
"screener.rank": "Rank",
"screener.score": "Score",
"screener.addCondition": "Add Condition",
"strategyLab.runBacktest": "Run Backtest",
"strategyLab.code": "Strategy Code"

// zh.json
"nav.strategyLab": "策略实验室",
"nav.workflow": "工作流",
"screener.filter": "筛选",
"screener.rank": "排名",
"screener.score": "评分",
"screener.addCondition": "添加条件",
"strategyLab.runBacktest": "运行回测",
"strategyLab.code": "策略代码"
```

- [ ] **Step 3: Verify build**

```bash
cd e:/coding/AStockPursue/frontend && npx next build 2>&1 | tail -5
```
Expected: Errors: 0

- [ ] **Step 4: Commit**

```bash
cd e:/coding/AStockPursue
git add frontend/lib/navigation.ts frontend/messages/
git commit -m "feat(frontend): add Strategy Lab to nav + i18n keys for new features"
```

---

## Verification Checklist

- [ ] `npx next build` — 0 errors
- [ ] `npx tsc --noEmit` — 0 errors (or pre-existing only)
- [ ] `/workflow/[id]` — 显示 DAG 画布，可拖拽节点，可连线
- [ ] `/strategy-lab` — 显示代码编辑器 + 回测面板 + 图表
- [ ] `/` Dashboard — 显示实时指数条 + WebSocket 连接
- [ ] `/screener` — 三种模式切换 + 条件构建器
- [ ] Go tests: `cd services/go && go test ./...` → 245/245
