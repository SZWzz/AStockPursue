/**
 * Workflow type definitions — mirrors the Python schema.
 */

export const PortType = {
  STOCK_LIST: "stock_list",
  DATE_RANGE: "date_range",
  PARAMS: "params",
  BOOL: "bool",
  DF_OHLCV: "df_ohlcv",
  DF_FACTOR: "df_factor",
  DF_RETURNS: "df_returns",
  FACTOR_RESULT: "factor_result",
  SIGNAL: "signal",
  BACKTEST_RESULT: "backtest_result",
  ATTRIBUTION: "attribution",
  TECHNICAL_INDICATOR: "technical_indicator",
  CORRELATION_MATRIX: "correlation_matrix",
  SENTIMENT: "sentiment",
  COMPARISON_RESULT: "comparison_result",
  ANY: "any",
} as const;
export type PortType = (typeof PortType)[keyof typeof PortType];

export function isCompatible(source: PortType, target: PortType): boolean {
  return target === PortType.ANY || source === target;
}

export type PortDirection = "input" | "output";
export type NodeStatus = "pending" | "running" | "done" | "error" | "cached";
export type RunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface NodePort {
  name: string;
  port_type: PortType;
  direction: PortDirection;
  required: boolean;
  description: string;
}

export interface NodeDefinition {
  node_type: string;
  category: string;
  label: string;
  description: string;
  icon: string;
  inputs: NodePort[];
  outputs: NodePort[];
  config_schema: Record<string, unknown>;
  resource_profile: string;
}

export interface WorkflowNodeData {
  id: string;
  node_type: string;
  label: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface WorkflowEdgeData {
  id: string;
  source: string;
  source_port: string;
  target: string;
  target_port: string;
}

export interface NodeRunResult {
  node_id: string;
  status: NodeStatus;
  summary: Record<string, unknown>;
  error_message: string;
  duration_ms: number;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  user_id: number;
  status: RunStatus;
  target_node_id: string | null;
  snapshot_nodes: WorkflowNodeData[];
  snapshot_edges: WorkflowEdgeData[];
  node_results: Record<string, NodeRunResult>;
  started_at: string;
  finished_at: string;
}

export type ConnectResult = { success: true } | { success: false; error: string };
