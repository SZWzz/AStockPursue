import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandItem {
  label: string;
  to: string;
  category: string;
}

const COMMANDS: CommandItem[] = [
  { label: "Dashboard", to: "/", category: "Pages" },
  { label: "Trading", to: "/trading", category: "Pages" },
  { label: "Strategy Lab", to: "/strategy-lab", category: "Pages" },
  { label: "Factor Mining", to: "/factor-mining", category: "Pages" },
  { label: "Paper Trading", to: "/paper-trading", category: "Pages" },
  { label: "Agent", to: "/agent", category: "Pages" },
  { label: "Screener", to: "/screener", category: "Pages" },
  { label: "Alpha Zoo", to: "/alpha-zoo", category: "Research" },
  { label: "Indicator Lab", to: "/indicator-lab", category: "Research" },
  { label: "Settings", to: "/settings", category: "Pages" },
  { label: "Data Sources", to: "/data-sources", category: "Pages" },
  { label: "Attribution", to: "/attribution", category: "Analysis" },
  { label: "Correlation", to: "/correlation", category: "Analysis" },
  { label: "Compare", to: "/compare", category: "Analysis" },
  { label: "Docs", to: "/docs", category: "Other" },
  { label: "Projects", to: "/projects", category: "Pages" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const filtered = COMMANDS.filter(
    (c) =>
      c.label.toLowerCase().includes(query.toLowerCase()) ||
      c.category.toLowerCase().includes(query.toLowerCase()),
  );

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    },
    [open],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const execute = (item: CommandItem) => {
    navigate(item.to);
    setOpen(false);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      execute(filtered[selectedIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-md bg-surface-3 border border-border rounded-xl shadow-lg overflow-hidden animate-scale-in">
        {/* Search input */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border-subtle">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleInputKeyDown}
            placeholder="Search pages..."
            className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/40 font-mono"
          />
          <kbd className="text-[10px] text-muted-foreground bg-surface-1 px-1.5 py-0.5 rounded font-mono">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">
              No pages found
            </div>
          )}
          {filtered.map((item, i) => (
            <button
              key={item.to}
              onClick={() => execute(item)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors text-sm",
                i === selectedIndex
                  ? "bg-primary/10 text-primary"
                  : "text-foreground hover:bg-muted/60",
              )}
            >
              <span className="flex-1">{item.label}</span>
              <span className="text-[10px] text-muted-foreground">{item.category}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
