import { useState, useRef, useEffect, useCallback } from "react";
import { Search, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { authHeaders } from "@/lib/apiAuth";

interface StockSymbol {
  code: string;
  name: string;
  market: string;
  type: string;
}

interface StockInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  multi?: boolean;
  className?: string;
}

export function StockInput({ value, onChange, placeholder = "600519.SH", multi = false, className }: StockInputProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSymbol[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    setSelectedIndex(-1);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(authHeaders() as Record<string, string>),
      };
      const res = await fetch(`/stock/search?q=${encodeURIComponent(q.trim())}`, { headers });
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      setResults(data.results || []);
      setOpen((data.results || []).length > 0);
    } catch {
      setResults([]);
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(query), 150);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, search]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const addSymbol = (symbol: StockSymbol) => {
    if (multi) {
      const current = value ? value.split(",").map((s) => s.trim()).filter(Boolean) : [];
      if (!current.includes(symbol.code)) {
        onChange(current.concat(symbol.code).join(", "));
      }
      setQuery("");
      setOpen(false);
      inputRef.current?.focus();
    } else {
      onChange(symbol.code);
      setQuery("");
      setOpen(false);
    }
  };

  const removeSymbol = (code: string) => {
    if (!multi) {
      onChange("");
      return;
    }
    const current = value.split(",").map((s) => s.trim()).filter((s) => s && s !== code);
    onChange(current.join(", "));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" && open && results.length > 0) {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp" && open && results.length > 0) {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex >= 0 && results.length > 0) {
        addSymbol(results[selectedIndex]);
      } else if (query.trim()) {
        // Allow free-text entry for symbols not in the search list (e.g. AAPL.US, BTC-USDT)
        addSymbol({ code: query.trim().toUpperCase(), name: query.trim(), market: "", type: "" });
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const selectedCodes = multi ? value.split(",").map((s) => s.trim()).filter(Boolean) : [];

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Selected chips (multi mode) */}
      {multi && selectedCodes.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1.5">
          {selectedCodes.map((code) => (
            <span
              key={code}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-primary/10 text-primary font-mono"
            >
              {code}
              <button
                type="button"
                onClick={() => removeSymbol(code)}
                className="hover:text-danger transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {/* Input */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            setTimeout(() => {
              if (query.trim() && (!multi || !value.split(",").includes(query.trim().toUpperCase()))) {
                addSymbol({ code: query.trim().toUpperCase(), name: query.trim(), market: "", type: "" });
              }
            }, 100);
          }}
          placeholder={multi ? "搜索或输入代码 (如 AAPL.US)..." : placeholder}
          className="w-full text-sm rounded-lg border border-border bg-background pl-8 pr-3 py-2 font-mono focus:outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/20 transition-all duration-150"
        />
        {loading && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
        )}
      </div>
      {/* Current value (single mode) */}
      {!multi && value && (
        <div className="mt-1 flex items-center gap-1.5">
          <span className="text-xs font-mono text-primary font-medium bg-primary/10 px-2 py-0.5 rounded">{value}</span>
          <button
            type="button"
            onClick={() => onChange("")}
            className="text-muted-foreground hover:text-danger transition-colors"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
      {/* Dropdown */}
      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-64 overflow-auto rounded-lg border bg-card shadow-lg animate-scale-in">
          {results.map((s, i) => (
            <div
              key={s.code}
              className={cn(
                "flex items-center justify-between px-3 py-2 cursor-pointer transition-colors text-sm",
                i === selectedIndex
                  ? "bg-primary/10 text-primary"
                  : "hover:bg-muted text-foreground"
              )}
              onClick={() => addSymbol(s)}
              onMouseEnter={() => setSelectedIndex(i)}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={cn(
                  "w-1.5 h-1.5 rounded-full shrink-0",
                  s.type === "index" ? "bg-warning" : s.market === "CN" ? "bg-emerald-400" : "bg-blue-400"
                )} />
                <span className="font-mono font-medium shrink-0">{s.code}</span>
                <span className="text-muted-foreground truncate">{s.name}</span>
              </div>
              <span className="text-xs text-muted-foreground/60 shrink-0 ml-2">
                {s.type === "index" ? "指数" : s.market === "CN" ? "A股" : "港股"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
