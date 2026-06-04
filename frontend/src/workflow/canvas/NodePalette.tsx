/**
 * NodePalette — left sidebar listing available node types, grouped by category.
 * Nodes can be dragged onto the canvas or clicked to add at centre.
 */

import { useState } from "react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import type { NodeDefinition } from "@/workflow/types/workflow";

// ── Category labels ──────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  data: "Data",
  alpha: "Alpha",
  filter: "Filter",
  strategy: "Strategy",
  execution: "Execution",
  analysis: "Analysis",
  deploy: "Deploy",
  control: "Control",
  output: "Output",
};

const CATEGORY_ORDER = ["data", "alpha", "filter", "strategy", "execution", "analysis", "deploy", "control", "output"];

// ── Draggable item ──────────────────────────────────────────────────────────

function DraggableNodeItem({ def }: { def: NodeDefinition }) {
  const addNode = useWorkflowStore((s) => s.addNode);

  const onDragStart = (event: React.DragEvent) => {
    event.dataTransfer.setData("application/reactflow-type", def.node_type);
    event.dataTransfer.effectAllowed = "move";
  };

  const onClick = () => {
    addNode(def.node_type, { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 });
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="flex items-center gap-2 px-2 py-1.5 rounded cursor-grab hover:bg-muted text-sm transition-colors"
      title={def.description}
    >
      <span className="text-xs w-5 text-center">{def.icon || "○"}</span>
      <span className="truncate">{def.label}</span>
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────

export default function NodePalette() {
  const nodeDefinitions = useWorkflowStore((s) => s.nodeDefinitions);
  const [search, setSearch] = useState("");

  // Group by category
  const grouped: Record<string, NodeDefinition[]> = {};
  for (const def of nodeDefinitions) {
    if (!grouped[def.category]) grouped[def.category] = [];
    grouped[def.category].push(def);
  }

  const filteredCategories = CATEGORY_ORDER.filter((cat) => grouped[cat]?.length);

  const visibleCategories = search
    ? Object.entries(grouped).filter(([, defs]) =>
        defs.some((d) => d.label.toLowerCase().includes(search.toLowerCase()) || d.description.toLowerCase().includes(search.toLowerCase()))
      )
    : filteredCategories.map((cat) => [cat, grouped[cat]] as const);

  return (
    <div className="h-full flex flex-col border-r bg-card">
      {/* Search */}
      <div className="p-2 border-b">
        <input
          type="text"
          placeholder="Search nodes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-2 py-1 text-xs rounded border bg-background"
        />
      </div>

      {/* Node list */}
      <div className="flex-1 overflow-y-auto p-1">
        {nodeDefinitions.length === 0 && (
          <p className="text-xs text-muted-foreground p-2">Loading node types...</p>
        )}
        {visibleCategories.map(([category, defs]) => (
          <div key={category} className="mb-2">
            <div className="px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              {CATEGORY_LABELS[category] || category}
            </div>
            {Array.isArray(defs) && defs.map((def) => (
              <DraggableNodeItem key={def.node_type} def={def} />
            ))}
          </div>
        ))}
      </div>

      {/* Node count footer */}
      <div className="border-t px-2 py-1 text-[10px] text-muted-foreground">
        {nodeDefinitions.length} node types
      </div>
    </div>
  );
}
