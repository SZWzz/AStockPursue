/**
 * ResultsPanel — bottom panel showing execution log and per-node output viewer.
 *
 * Collapsible by default.  Renders a timeline of execution events and allows
 * the user to click a log entry to view that node's detailed results.
 */

import { useState } from "react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import { cn } from "@/lib/utils";

const LEVEL_STYLES: Record<string, string> = {
  info: "text-muted-foreground",
  success: "text-green-600 dark:text-green-400",
  error: "text-red-600 dark:text-red-400",
};

export default function ResultsPanel() {
  const executionLog = useWorkflowStore((s) => s.executionLog);
  const runStatus = useWorkflowStore((s) => s.runStatus);
  const nodeResults = useWorkflowStore((s) => s.nodeResults);
  const [collapsed, setCollapsed] = useState(false);
  const [selectedLogIdx, setSelectedLogIdx] = useState<number | null>(null);

  if (runStatus === "idle" && executionLog.length === 0) return null;

  return (
    <div className={cn("border-t bg-card transition-all", collapsed ? "h-8" : "h-48")}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1 border-b">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {collapsed ? "▸" : "▾"} Execution Log
          </button>
          {runStatus === "running" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 animate-pulse">
              Running
            </span>
          )}
          {runStatus === "completed" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              Completed
            </span>
          )}
          {runStatus === "error" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
              Error
            </span>
          )}
        </div>
        <span className="text-[10px] text-muted-foreground">{executionLog.length} events</span>
      </div>

      {!collapsed && (
        <div className="flex h-[calc(100%-2rem)]">
          {/* Log list */}
          <div className="w-1/2 border-r overflow-y-auto">
            {executionLog.length === 0 && (
              <p className="text-xs text-muted-foreground p-3">No events yet</p>
            )}
            {executionLog.map((entry, idx) => (
              <div
                key={idx}
                onClick={() => setSelectedLogIdx(idx)}
                className={cn(
                  "px-3 py-1 text-xs cursor-pointer hover:bg-muted transition-colors border-b border-border/50",
                  selectedLogIdx === idx && "bg-muted",
                  LEVEL_STYLES[entry.level]
                )}
              >
                <span className="text-[10px] text-muted-foreground mr-1">[{entry.nodeId.slice(0, 8)}]</span>
                {entry.message}
              </div>
            ))}
          </div>

          {/* Detail view */}
          <div className="w-1/2 overflow-y-auto p-3">
            {selectedLogIdx !== null && executionLog[selectedLogIdx] ? (
              <div>
                <h4 className="text-xs font-semibold mb-1">
                  Node: {executionLog[selectedLogIdx].nodeId}
                </h4>
                <pre className="text-[10px] bg-muted p-2 rounded overflow-x-auto max-h-32">
                  {JSON.stringify(
                    nodeResults[executionLog[selectedLogIdx].nodeId] || {},
                    null,
                    1
                  )}
                </pre>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center pt-4">
                Click a log entry to view details
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
