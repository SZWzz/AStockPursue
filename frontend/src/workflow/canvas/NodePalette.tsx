/**
 * NodePalette — left sidebar listing available node types, grouped by category.
 * Nodes can be dragged onto the canvas or clicked to add at centre.
 */

import { useMemo, useState } from "react";
import { useWorkflowStore } from "@/workflow/store/workflowStore";
import { useI18n } from "@/lib/i18n";
import type { NodeDefinition } from "@/workflow/types/workflow";
import {
  Target, BarChart3, Layers, Database, Microscope, PieChart, Filter,
  TrendingUp, MessageSquare, Bot, GitBranch, FlaskConical, GitCompare,
  Newspaper, Globe, Send, FileText, CircleDollarSign, Bell, Download,
  Plug, Activity, Award,
} from "lucide-react";

// ── Category labels (English fallback, overridden by i18n wfCat_* keys) ──────

const CATEGORY_LABELS_FALLBACK: Record<string, string> = {
  data: "Data",
  alpha: "Alpha",
  filter: "Filter",
  strategy: "Strategy",
  execution: "Execution",
  analysis: "Analysis",
  deploy: "Deploy",
  control: "Control",
  output: "Output",
  visualization: "Visualization",
};

const CATEGORY_ORDER = ["data", "alpha", "filter", "strategy", "execution", "analysis", "deploy", "control", "output", "visualization"];

// ── i18n helpers ──────────────────────────────────────────────────────────────

/** Look up node label from i18n: wfNode_{node_type} → fallback to def.label */
function tNode(t: Record<string, string>, nodeType: string, fallback: string): string {
  const key = `wfNode_${nodeType}`;
  return (t as any)[key] || fallback;
}

/** Look up node description from i18n: wfNode_{node_type}_desc → fallback to def.description */
function tNodeDesc(t: Record<string, string>, nodeType: string, fallback: string): string {
  const key = `wfNode_${nodeType}_desc`;
  return (t as any)[key] || fallback;
}

/** Look up category label from i18n: wfCat_{category} → fallback */
function tCat(t: Record<string, string>, category: string): string {
  const key = `wfCat_${category}`;
  return (t as any)[key] || CATEGORY_LABELS_FALLBACK[category] || category;
}

// ── Icon map ──────────────────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ComponentType<any>> = {
  Target, BarChart3, Layers, Database, Microscope, PieChart, Filter,
  TrendingUp, MessageSquare, Bot, GitBranch, FlaskConical, GitCompare,
  Newspaper, Globe, Send, FileText, CircleDollarSign, Bell, Download,
  Plug, Activity, Award,
};

function NodeIcon({ name, className }: { name?: string; className?: string }) {
  if (!name) return <span className={className}>○</span>;
  const Icon = ICON_MAP[name];
  return Icon ? <Icon className={className} /> : <span className={className}>○</span>;
}

// ── Draggable item ──────────────────────────────────────────────────────────

function DraggableNodeItem({ def, t }: { def: NodeDefinition; t: Record<string, string> }) {
  const addNode = useWorkflowStore((s) => s.addNode);

  const onDragStart = (event: React.DragEvent) => {
    event.dataTransfer.setData("application/reactflow-type", def.node_type);
    event.dataTransfer.effectAllowed = "move";
  };

  const onClick = () => {
    addNode(def.node_type, { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 });
  };

  const label = tNode(t, def.node_type, def.label);
  const desc = tNodeDesc(t, def.node_type, def.description);

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="flex items-center gap-2 px-2 py-1.5 rounded cursor-grab hover:bg-muted text-sm transition-colors"
      title={desc}
    >
      <NodeIcon name={def.icon} className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate">{label}</span>
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────

export default function NodePalette() {
  const nodeDefinitions = useWorkflowStore((s) => s.nodeDefinitions);
  const [search, setSearch] = useState("");
  const { t } = useI18n();

  const nodeUsageCount = useWorkflowStore((s) => s.nodeUsageCount);

  // Group by category, sort by usage frequency within each category
  const grouped = useMemo(() => {
    const g: Record<string, NodeDefinition[]> = {};
    for (const def of nodeDefinitions) {
      if (!g[def.category]) g[def.category] = [];
      g[def.category].push(def);
    }
    // Sort each category: most-used first, then alphabetically
    for (const cat of Object.keys(g)) {
      g[cat].sort((a, b) => {
        const ua = nodeUsageCount[a.node_type] || 0;
        const ub = nodeUsageCount[b.node_type] || 0;
        if (ua !== ub) return ub - ua;  // descending by usage
        return (a.label || a.node_type).localeCompare(b.label || b.node_type);
      });
    }
    return g;
  }, [nodeDefinitions, nodeUsageCount]);

  const visibleCategories = useMemo(() => {
    if (search) {
      const q = search.toLowerCase();
      return Object.entries(grouped)
        .map(([cat, defs]) => [
          cat,
          defs.filter((d) => {
            const label = tNode(t, d.node_type, d.label);
            const desc = tNodeDesc(t, d.node_type, d.description);
            return label.toLowerCase().includes(q) ||
                   desc.toLowerCase().includes(q) ||
                   d.node_type.toLowerCase().includes(q);
          }),
        ] as const)
        .filter(([, defs]) => defs.length > 0);
    }
    const filtered = CATEGORY_ORDER.filter((cat) => grouped[cat]?.length);
    return filtered.map((cat) => [cat, grouped[cat]] as const);
  }, [grouped, search, t]);

  const searchPlaceholder = (t as any).wfNode_searchPlaceholder || "Search nodes...";

  return (
    <div className="h-full flex flex-col border-r bg-card">
      {/* Search */}
      <div className="p-2 border-b">
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-2 py-1 text-xs rounded border bg-background"
        />
      </div>

      {/* Node list */}
      <div className="flex-1 overflow-y-auto p-1">
        {nodeDefinitions.length === 0 && (
          <p className="text-xs text-muted-foreground p-2">{((t as any).wfNode_loading || "Loading node types...")}</p>
        )}
        {visibleCategories.map(([category, defs]) => (
          <div key={category} className="mb-2">
            <div className="px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              {tCat(t, category)}
            </div>
            {Array.isArray(defs) && defs.map((def) => (
              <DraggableNodeItem key={def.node_type} def={def} t={t} />
            ))}
          </div>
        ))}
      </div>

      {/* Node count footer */}
      <div className="border-t px-2 py-1 text-[10px] text-muted-foreground">
        {nodeDefinitions.length} {((t as any).wfNode_nodeTypes || "node types")}
      </div>
    </div>
  );
}
