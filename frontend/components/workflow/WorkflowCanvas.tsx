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
