import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Workflow, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ExportToWorkflowButtonProps {
  sourcePage: string;
  config: Record<string, unknown>;
  className?: string;
}

export function ExportToWorkflowButton({
  sourcePage,
  config,
  className,
}: ExportToWorkflowButtonProps) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      const data = await api.createWorkflowFromPage({
        source_page: sourcePage,
        config,
      });
      if (data?.redirect) {
        navigate(data.redirect);
      }
    } catch (e) {
      console.error("Failed to export to workflow:", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border hover:bg-primary/5 hover:border-primary/30 transition-colors disabled:opacity-50",
        className
      )}
      title="在工作流画布中打开，可串联回测、对比、归因等节点"
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Workflow className="h-3.5 w-3.5" />
      )}
      导出为工作流节点
    </button>
  );
}
