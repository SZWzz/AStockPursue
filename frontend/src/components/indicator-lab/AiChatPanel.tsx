import { useState, useRef } from "react";
import { Send, Loader2, X, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { useI18n } from "@/lib/i18n";

interface AiChatPanelProps {
  visible: boolean;
  onToggle: () => void;
  generating: boolean;
  onGenerate: (prompt: string) => void;
  onCancel: () => void;
}

export function AiChatPanel({ visible, onToggle, generating, onGenerate, onCancel }: AiChatPanelProps) {
  const { t } = useI18n();
  const [prompt, setPrompt] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const trimmed = prompt.trim();
    if (!trimmed || generating) return;
    onGenerate(trimmed);
    setPrompt("");
  };

  return (
    <div className="border border-border rounded-2xl bg-card shadow-sm shrink-0 overflow-hidden">
      {/* Toggle bar */}
      <button
        onClick={onToggle}
        className="flex items-center gap-1.5 w-full px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
      >
        <Sparkles className="h-3 w-3" />
        <span className="flex-1 text-left">{t.aiChatTitle}</span>
        {visible ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
      </button>

      {/* Chat input */}
      {visible && (
        <div className="px-3 pb-2.5 pt-0">
          <div className="flex items-center gap-1.5">
            <input
              ref={inputRef}
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder={t.aiChatPlaceholder}
              disabled={generating}
              className="flex-1 text-xs rounded-lg border border-border bg-background px-3 py-2 focus:outline-none focus:border-primary/50 transition-colors disabled:opacity-50"
            />
            {generating ? (
              <button onClick={onCancel} className="btn-sm btn-danger shrink-0 flex items-center gap-1">
                <X className="h-3 w-3" />
                {t.cancel}
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!prompt.trim()}
                className="btn-sm btn-primary shrink-0 flex items-center gap-1 disabled:opacity-50"
              >
                {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
                {t.aiChatSend}
              </button>
            )}
          </div>
          {generating && (
            <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t.aiChatGenerating}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
