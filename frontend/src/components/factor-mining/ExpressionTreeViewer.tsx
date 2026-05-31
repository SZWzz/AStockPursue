import { cn } from "@/lib/utils";

interface ExpressionNode {
  op?: string;
  children?: ExpressionNode[];
  value?: number;
  feature_id?: string;
  window?: number;
}

interface Props {
  tree: ExpressionNode;
  className?: string;
}

function TreeNode({ node, depth = 0 }: { node: ExpressionNode; depth: number }) {
  const isLeaf = !node.op;

  const colorClasses =
    isLeaf && node.feature_id
      ? "bg-blue-500/10 border-blue-500/30 text-blue-600 dark:text-blue-400"
      : isLeaf && node.value != null
        ? "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400"
        : "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400";

  const label = isLeaf
    ? node.feature_id || `${node.value?.toFixed(3)}`
    : (node.op || "?").replace("_", " ");

  return (
    <div className="flex flex-col items-center">
      <div className={cn("px-2 py-1 rounded border text-xs font-mono", colorClasses)}>
        {label}
        {node.window && node.window !== 20 && (
          <span className="text-[10px] ml-1 opacity-60">w{node.window}</span>
        )}
      </div>
      {node.children && node.children.length > 0 && (
        <div className="flex flex-col items-center mt-1">
          {/* Connector line */}
          <div className="w-px h-2 bg-border" />
          <div className="flex gap-3 items-start">
            {node.children.map((child, i) => (
              <TreeNode key={i} node={child} depth={depth + 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ExpressionTreeViewer({ tree, className }: Props) {
  if (!tree || (!tree.op && !tree.feature_id && tree.value == null)) {
    return null;
  }

  return (
    <div className={cn("flex flex-col items-center py-3 overflow-x-auto", className)}>
      <span className="text-[10px] text-muted-foreground mb-2">Expression Tree</span>
      <TreeNode node={tree} depth={0} />
    </div>
  );
}
