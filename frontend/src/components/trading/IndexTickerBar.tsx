import { useEffect, useState, useCallback, useRef } from "react";
import { TrendingUp, TrendingDown, Minus, Settings, X, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type IndexItem } from "@/lib/api";

interface Props {
  indices: IndexItem[];
  onRefresh: () => void;
}

/** Horizontal scrolling index ticker bar with edit/settings popover. */
export function IndexTickerBar({ indices, onRefresh }: Props) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [editList, setEditList] = useState<IndexItem[]>([]);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setEditList([...indices]);
  }, [indices]);

  // Poll every 15s
  useEffect(() => {
    if (indices.length === 0) onRefresh();
    const id = setInterval(onRefresh, 15000);
    return () => clearInterval(id);
  }, [onRefresh, indices.length]);

  const saveEdit = async () => {
    const clean = editList.filter((it) => it.code && it.name);
    setEditList(clean);
    try {
      await api.saveIndicesConfig(clean);
      setEditing(false);
      setTimeout(onRefresh, 300);
    } catch { /* ignore */ }
  };

  const addToEdit = () => {
    if (!newCode.trim()) return;
    setEditList((prev) => [...prev, { code: newCode.trim().toUpperCase(), name: newName.trim() || newCode.trim().toUpperCase(), price: 0, change_pct: 0 }]);
    setNewCode("");
    setNewName("");
  };

  const removeFromEdit = (code: string) => {
    setEditList((prev) => prev.filter((it) => it.code !== code));
  };

  return (
    <div className="relative border-b bg-muted/20">
      {/* Scrollable ticker */}
      <div ref={barRef} className="flex items-center gap-1 px-2 py-1.5 overflow-x-auto text-xs">
        {indices.map((it) => {
          const isUp = it.change_pct > 0;
          const isDown = it.change_pct < 0;
          const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
          return (
            <div
              key={it.code}
              className={cn(
                "flex items-center gap-1 px-2 py-0.5 rounded whitespace-nowrap shrink-0",
                isUp && "text-up", isDown && "text-down"
              )}
            >
              <span className="font-medium max-w-[60px] truncate">{it.name}</span>
              <span className="font-mono">{it.price ? it.price.toFixed(2) : "—"}</span>
              <Icon className="h-2.5 w-2.5" />
              <span className="font-mono">{it.change_pct ? (it.change_pct > 0 ? "+" : "") + it.change_pct.toFixed(2) + "%" : "—"}</span>
            </div>
          );
        })}
        <button
          onClick={() => setEditing(!editing)}
          className="p-0.5 rounded text-muted-foreground hover:text-primary transition shrink-0 ml-1"
          title={t.tradingEditIndices || "Edit indices"}
        >
          <Settings className="h-3 w-3" />
        </button>
      </div>

      {/* Edit popover */}
      {editing && (
        <div className="absolute top-full right-2 mt-1 z-50 w-72 border rounded-lg bg-card shadow-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium">{t.tradingEditIndices || "Edit Indices"}</span>
            <button onClick={() => setEditing(false)} className="text-muted-foreground hover:text-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="space-y-1 max-h-48 overflow-auto">
            {editList.map((it) => (
              <div key={it.code} className="flex items-center gap-2 text-xs">
                <span className="font-mono w-24 truncate">{it.code}</span>
                <span className="flex-1 truncate">{it.name}</span>
                <button onClick={() => removeFromEdit(it.code)} className="text-muted-foreground hover:text-danger">
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              placeholder="000001.SH"
              className="flex-1 text-xs rounded border px-2 py-1 bg-background"
            />
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Name"
              className="w-20 text-xs rounded border px-2 py-1 bg-background"
            />
            <button onClick={addToEdit} className="p-1 text-primary hover:bg-primary/10 rounded">
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          <button
            onClick={saveEdit}
            className="w-full text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {t.llmSaveSettings || "Save"}
          </button>
        </div>
      )}
    </div>
  );
}
