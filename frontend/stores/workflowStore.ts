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
