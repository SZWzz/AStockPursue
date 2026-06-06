/**
 * Alpha Zoo — browse / detail / bench views.
 *
 * Routing model: a single page component, three URL shapes:
 *   /alpha-zoo                 → browse view
 *   /alpha-zoo/bench           → bench runner
 *   /alpha-zoo/:alphaId        → alpha detail
 *
 * The bench view uses a raw EventSource rather than the shared `useSSE` hook
 * because that hook hard-codes the agent's known event types (text_delta,
 * tool_call, …) and would silently drop the alpha bench events
 * (`progress`, `result`, `done`, `error`). The swarm page uses the same
 * raw-EventSource pattern (frontend/src/pages/Agent.tsx).
 */

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  Layers,
  Search,
  Play,
  ArrowLeft,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Library,
  Download,
  Square,
  History,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  api,
  type AlphaSummary,
  type AlphaDetailResponse,
  type AlphaBenchResult,
  type AlphaBenchTopRow,
  type BenchHistoryItem,
} from "@/lib/api";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";
import { useDarkMode } from "@/hooks/useDarkMode";
import { useI18n } from "@/lib/i18n";

/* ---------- Zoo card keys (resolved via i18n) ---------- */

interface ZooCardKey {
  id: string;
  titleKey: string;
  descKey: string;
  approxCount: number;
  accent: string;
}

const ZOO_CARD_KEYS: ZooCardKey[] = [
  {
    id: "qlib158",
    titleKey: "azZoo_qlib158_title",
    descKey: "azZoo_qlib158_desc",
    approxCount: 154,
    accent: "from-sky-500/20 to-sky-500/5",
  },
  {
    id: "alpha101",
    titleKey: "azZoo_alpha101_title",
    descKey: "azZoo_alpha101_desc",
    approxCount: 101,
    accent: "from-emerald-500/20 to-emerald-500/5",
  },
  {
    id: "gtja191",
    titleKey: "azZoo_gtja191_title",
    descKey: "azZoo_gtja191_desc",
    approxCount: 191,
    accent: "from-amber-500/20 to-amber-500/5",
  },
  {
    id: "academic",
    titleKey: "azZoo_academic_title",
    descKey: "azZoo_academic_desc",
    approxCount: 6,
    accent: "from-violet-500/20 to-violet-500/5",
  },
];

const UNIVERSE_OPTION_KEYS = [
  { value: "csi300", labelKey: "azUniverse_csi300" },
  { value: "sp500", labelKey: "azUniverse_sp500" },
  { value: "btc-usdt", labelKey: "azUniverse_btc" },
];

const PAGE_SIZE = 50;

/* ---------- Helpers ---------- */

function fmtNum(v: unknown, digits = 3): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function metaString(meta: Record<string, unknown>, key: string): string {
  const v = meta[key];
  if (v === undefined || v === null || v === "") return "—";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

/** Resolve a dynamic i18n key against the active bundle; falls back to key. */
function tkey(t: Record<string, string>, key: string): string {
  return t[key] || key;
}

/** Translate a theme name via i18n azTheme_<name> key; falls back to original. */
function translateTheme(t: Record<string, string>, theme: string): string {
  return t[`azTheme_${theme}`] || theme;
}

/* ---------- Page entry ---------- */

export function AlphaZoo() {
  const params = useParams<{ alphaId?: string }>();
  const { pathname } = useLocation();

  if (pathname === "/alpha-zoo/bench") {
    return <BenchView />;
  }
  if (params.alphaId) {
    return <DetailView alphaId={params.alphaId} />;
  }
  return <BrowseView />;
}

/* ---------- Browse view ---------- */

function BrowseView() {
  const { t } = useI18n();
  const [alphas, setAlphas] = useState<AlphaSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [zooFilter, setZooFilter] = useState<string>("");
  const [themeFilter, setThemeFilter] = useState<string>("");
  const [universeFilter, setUniverseFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [total, setTotal] = useState<number>(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .listAlphas({
        zoo: zooFilter || undefined,
        theme: themeFilter || undefined,
        universe: universeFilter || undefined,
        limit: 1000,
      })
      .then((res) => {
        if (!alive) return;
        setAlphas(res.alphas || []);
        setTotal(res.total || 0);
        setVisibleCount(PAGE_SIZE);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        const msg = err instanceof Error ? err.message : "Failed to load alphas";
        toast.error(msg);
        setAlphas([]);
        setTotal(0);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [zooFilter, themeFilter, universeFilter]);

  const themeOptions = useMemo(() => {
    const set = new Set<string>();
    for (const a of alphas) for (const t of a.theme || []) set.add(t);
    return Array.from(set).sort();
  }, [alphas]);

  const universeOptions = useMemo(
    () => UNIVERSE_OPTION_KEYS.map((u) => ({ value: u.value, label: tkey(t, u.labelKey) })),
    [t],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return alphas;
    return alphas.filter(
      (a) =>
        a.id.toLowerCase().includes(q) ||
        (a.nickname || "").toLowerCase().includes(q),
    );
  }, [alphas, search]);

  const visible = filtered.slice(0, visibleCount);

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-8">
      {/* Hero */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide">
          <Layers className="h-3.5 w-3.5" aria-hidden="true" /> {t.azBreadcrumb}
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
          {t.azHeroTitle.replace("{n}", String(total > 0 ? total : 452))}
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">{t.azHeroDesc}</p>
      </div>

      {/* Zoo cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {ZOO_CARD_KEYS.map((z) => {
          const active = zooFilter === z.id;
          return (
            <button
              key={z.id}
              type="button"
              onClick={() => setZooFilter(active ? "" : z.id)}
              className={cn(
                "text-left border rounded-xl p-4 space-y-2 transition bg-gradient-to-br",
                z.accent,
                "hover:border-primary/50",
                active && "border-primary ring-1 ring-primary/30",
              )}
            >
              <div className="flex items-center justify-between">
                <Library className="h-5 w-5 text-primary" aria-hidden="true" />
                <span className="text-xs font-mono text-muted-foreground">
                  {z.approxCount}
                </span>
              </div>
              <h3 className="font-semibold text-sm leading-tight">{tkey(t, z.titleKey)}</h3>
              <p className="text-xs text-muted-foreground line-clamp-3">
                {tkey(t, z.descKey)}
              </p>
            </button>
          );
        })}
      </div>

      {/* Filter bar */}
      <div className="flex flex-col md:flex-row md:items-end gap-3 border rounded-xl p-4 bg-card">
        <div className="flex-1 min-w-0">
          <label htmlFor="alpha-search" className="text-xs text-muted-foreground block mb-1">
            {t.azSearch}
          </label>
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              id="alpha-search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setVisibleCount(PAGE_SIZE);
              }}
              placeholder={t.azFilterPlaceholder}
              className="w-full pl-9 pr-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>
        <div className="md:w-40">
          <label htmlFor="alpha-zoo-filter" className="text-xs text-muted-foreground block mb-1">{t.azZoo}</label>
          <select
            id="alpha-zoo-filter"
            value={zooFilter}
            onChange={(e) => setZooFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">{t.azAllZoos}</option>
            {ZOO_CARD_KEYS.map((z) => (
              <option key={z.id} value={z.id}>
                {tkey(t, z.titleKey)}
              </option>
            ))}
          </select>
        </div>
        <div className="md:w-40">
          <label htmlFor="alpha-theme-filter" className="text-xs text-muted-foreground block mb-1">
            {t.azTheme}
          </label>
          <select
            id="alpha-theme-filter"
            value={themeFilter}
            onChange={(e) => setThemeFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">{t.azAllThemes}</option>
            {themeOptions.map((tname) => (
              <option key={tname} value={tname}>
                {translateTheme(t, tname)}
              </option>
            ))}
          </select>
        </div>
        <div className="md:w-44">
          <label htmlFor="alpha-universe-filter" className="text-xs text-muted-foreground block mb-1">
            {t.azUniverse}
          </label>
          <select
            id="alpha-universe-filter"
            value={universeFilter}
            onChange={(e) => setUniverseFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">{t.azAllUniverses}</option>
            {universeOptions.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </div>
        <Link
          to="/alpha-zoo/bench"
          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition"
        >
          <Play className="h-3.5 w-3.5" aria-hidden="true" /> {t.azRunBench}
        </Link>
      </div>

      {/* Table */}
      <div className="border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" aria-label="Alpha catalogue">
            <caption className="sr-only">Alpha catalogue</caption>
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="text-left px-4 py-2.5 text-muted-foreground">{t.azColId}</th>
                <th className="text-left px-4 py-2.5 text-muted-foreground">{t.azColZoo}</th>
                <th className="text-left px-4 py-2.5 text-muted-foreground">{t.azColTheme}</th>
                <th className="text-left px-4 py-2.5 text-muted-foreground hidden md:table-cell">{t.azColUniverse}</th>
                <th className="text-right px-4 py-2.5 text-muted-foreground">{t.azColDecay}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin inline mr-2" aria-hidden="true" />
                    {t.azLoading}
                  </td>
                </tr>
              ) : visible.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    {t.azNoMatch}
                  </td>
                </tr>
              ) : (
                visible.map((a) => (
                  <tr
                    key={`${a.zoo}:${a.id}`}
                    className="border-b last:border-0 hover:bg-muted/20"
                  >
                    <td className="px-4 py-2 font-mono text-xs">
                      <Link
                        to={`/alpha-zoo/${encodeURIComponent(a.id)}`}
                        className="text-primary hover:underline"
                      >
                        {a.id}
                      </Link>
                      {a.nickname && (
                        <span className="ml-2 text-muted-foreground font-sans">
                          {a.nickname}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs">{a.zoo}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {(a.theme || []).map(th => translateTheme(t, th)).join(", ") || "—"}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground hidden md:table-cell">
                      {(a.universe || []).map(u => tkey(t, `azUniverse_${u}`)).join(", ") || "—"}
                    </td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums text-xs">
                      {a.decay_horizon ?? "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {!loading && visible.length < filtered.length && (
          <div className="border-t p-3 flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {t.azShowing.replace("{visible}", String(visible.length)).replace("{total}", String(filtered.length))}
            </span>
            <button
              type="button"
              onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
              className="px-3 py-1 rounded-md border hover:bg-muted hover:text-foreground transition"
            >
              {t.azLoadMore}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Detail view ---------- */

interface DetailProps {
  alphaId: string;
}

function DetailView({ alphaId }: DetailProps) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<AlphaDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .getAlpha(alphaId)
      .then((res) => {
        if (alive) setDetail(res);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        const msg = err instanceof Error ? err.message : "Failed to load alpha";
        setError(msg);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [alphaId]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin mr-2" aria-hidden="true" /> {t.azDetailLoading.replace("{id}", alphaId)}
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="p-8 max-w-3xl mx-auto space-y-4">
        <Link to="/alpha-zoo" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> {t.azBack}
        </Link>
        <div className="border rounded-xl p-6 bg-card">
          <h2 className="font-semibold text-sm mb-1 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" /> {t.azDetailError}
          </h2>
          <p className="text-sm text-muted-foreground">{error || t.unknownError}</p>
        </div>
      </div>
    );
  }

  const a = detail.alpha;
  const meta = a.meta || {};
  const formulaLatex = (meta["formula_latex"] as string | undefined) || "";
  const nickname = (meta["nickname"] as string | undefined) || "";
  const firstUniverse = ((meta["universe"] as string[] | undefined) || [])[0] || "";

  const benchHref = firstUniverse
    ? `/alpha-zoo/bench?zoo=${encodeURIComponent(a.zoo)}&universe=${encodeURIComponent(firstUniverse)}&period=2020-2025`
    : `/alpha-zoo/bench?zoo=${encodeURIComponent(a.zoo)}&period=2020-2025`;

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <Link
          to="/alpha-zoo"
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> {t.azBack}
        </Link>
        <button
          type="button"
          onClick={() => navigate(benchHref)}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 transition"
        >
          <Play className="h-3.5 w-3.5" aria-hidden="true" /> {t.azRunBench}
        </button>
      </div>

      {/* Title */}
      <div className="space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="font-mono text-xl md:text-2xl font-bold tracking-tight">
            {a.id}
          </h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
            {a.zoo}
          </span>
        </div>
        {nickname && (
          <p className="text-sm text-muted-foreground">{nickname}</p>
        )}
      </div>

      {/* Formula */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">{t.azFormula}</h2>
        <pre className="border rounded-xl bg-muted/30 p-4 overflow-x-auto text-xs leading-relaxed">
          <code>{formulaLatex || t.azNoFormula}</code>
        </pre>
      </section>

      {/* Metadata */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">{t.azMetadata}</h2>
        <div className="border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              <MetaRow label={t.azMetaTheme} value={metaString(meta, "theme")} />
              <MetaRow label={t.azMetaUniverse} value={metaString(meta, "universe")} />
              <MetaRow label={t.azMetaFreq} value={metaString(meta, "frequency")} />
              <MetaRow label={t.azMetaDecay} value={metaString(meta, "decay_horizon")} />
              <MetaRow label={t.azMetaWarmup} value={metaString(meta, "min_warmup_bars")} />
              <MetaRow label={t.azMetaSector} value={metaString(meta, "requires_sector")} />
              <MetaRow label={t.azMetaModule} value={a.module_path || "—"} />
              <MetaRow label={t.azMetaNotes} value={metaString(meta, "notes")} last />
            </tbody>
          </table>
        </div>
      </section>

      {/* Source code */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">{t.azSourceCode}</h2>
        <details className="border rounded-xl bg-card group">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium hover:bg-muted/40 select-none">
            {t.azViewSource.replace("{n}", String((detail.source_code || "").split("\n").length))}
          </summary>
          <pre className="border-t bg-muted/30 p-4 overflow-x-auto text-xs leading-relaxed">
            <code>{detail.source_code || t.azNoSource}</code>
          </pre>
        </details>
      </section>
    </div>
  );
}

function MetaRow({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <tr className={cn(!last && "border-b", "hover:bg-muted/20")}>
      <td className="px-4 py-2 text-xs text-muted-foreground w-1/3">{label}</td>
      <td className="px-4 py-2 text-xs font-mono break-all">{value}</td>
    </tr>
  );
}

/* ---------- Bench view ---------- */

type BenchStatus = "idle" | "submitting" | "streaming" | "done" | "error";

interface BenchProgress {
  n_done: number;
  n_total: number;
  current_alpha_id?: string;
}

function BenchView() {
  const { t } = useI18n();
  const { search: locSearch } = useLocation();
  const initial = useMemo(() => {
    const q = new URLSearchParams(locSearch);
    return {
      zoo: q.get("zoo") || "alpha101",
      universe: q.get("universe") || "csi300",
      period: q.get("period") || "2020-2025",
      top: Number(q.get("top") || "20"),
    };
  }, [locSearch]);

  const [zoo, setZoo] = useState(initial.zoo);
  const [universe, setUniverse] = useState(initial.universe);
  const [period, setPeriod] = useState(initial.period);
  const [top, setTop] = useState<number>(initial.top);

  const [status, setStatus] = useState<BenchStatus>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<BenchProgress | null>(null);
  const [result, setResult] = useState<AlphaBenchResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const doneRef = useRef(false);
  const cancelledRef = useRef(false);
  useEffect(() => { return () => { cancelledRef.current = true; }; }, []);

  // History
  const [history, setHistory] = useState<BenchHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const universeOptions = useMemo(
    () => UNIVERSE_OPTION_KEYS.map((u) => ({ value: u.value, label: tkey(t, u.labelKey) })),
    [t],
  );

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, []);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await api.listBenchHistory(50, 0);
      setHistory(data.history || []);
    } catch { /* ignore */ }
    finally { setHistoryLoading(false); }
  };

  useEffect(() => {
    loadHistory().catch(() => {});
  }, []);

  // Reload history when a bench completes
  useEffect(() => {
    if (status === "done") loadHistory().catch(() => {});
  }, [status]);

  const startBench = async (e: FormEvent) => {
    e.preventDefault();
    if (status === "submitting" || status === "streaming") return;
    setStatus("submitting");
    setProgress(null);
    setResult(null);
    setFormError(null);
    doneRef.current = false;
    sourceRef.current?.close();
    sourceRef.current = null;
    const safeTop = Number.isFinite(top) && top > 0 ? top : 20;
    try {
      const res = await api.createAlphaBench({
        zoo,
        universe,
        period,
        top: safeTop,
      });
      // Guard against unmount during async gap
      if (cancelledRef.current) return;
      setJobId(res.job_id);
      attachStream(res.job_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t.azBenchStartFailed;
      if (msg.toLowerCase().includes("single-asset")) {
        setFormError(t.azBenchSingleAsset.replace("{msg}", msg));
      } else {
        toast.error(msg);
      }
      setStatus("error");
    }
  };

  const attachStream = (newJobId: string) => {
    setStatus("streaming");
    const url = api.alphaBenchStreamUrl(newJobId);
    const source = new EventSource(url);
    sourceRef.current = source;

    source.addEventListener("progress", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as BenchProgress;
        setProgress(data);
      } catch {
        /* ignore */
      }
    });

    source.addEventListener("result", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as AlphaBenchResult;
        setResult(data);
      } catch {
        /* ignore */
      }
    });

    source.addEventListener("done", () => {
      doneRef.current = true;
      setStatus("done");
      source.close();
      sourceRef.current = null;
    });

    source.addEventListener("error", (e) => {
      if (doneRef.current) {
        source.close();
        sourceRef.current = null;
        return;
      }
      let msg = t.azBenchStreamError;
      try {
        const data = JSON.parse((e as MessageEvent).data || "{}");
        if (typeof data.message === "string") msg = data.message;
      } catch {
        /* network-level error, no payload */
      }
      toast.error(msg);
      setStatus("error");
      source.close();
      sourceRef.current = null;
    });
  };

  const cancelBench = async () => {
    if (!jobId) return;
    try {
      await api.cancelAlphaBench(jobId);
      sourceRef.current?.close();
      sourceRef.current = null;
      setStatus("idle");
      toast.info("Bench cancelled");
    } catch {
      toast.error("Failed to cancel");
    }
  };

  const exportCsv = () => {
    if (!result) return;
    const rows = result.top5_by_ir || [];
    const headers = ["Alpha ID", "IC Mean", "IR", "Theme", "Category"];
    const csvLines = [headers.join(",")];
    for (const r of rows) {
      csvLines.push([
        r.id,
        r.ic_mean.toFixed(4),
        r.ir.toFixed(4),
        (r.theme || []).join(";"),
        r.category,
      ].join(","));
    }
    csvLines.push("");
    csvLines.push(`Alive,${result.alive},Reversed,${result.reversed},Dead,${result.dead}`);
    const blob = new Blob(["﻿" + csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `alpha-bench-${zoo}-${universe}-${period}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const busy = status === "submitting" || status === "streaming";

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-6">
      <Link
        to="/alpha-zoo"
        className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> {t.azBack}
      </Link>

      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide">
          <Play className="h-3.5 w-3.5" aria-hidden="true" /> {t.azBenchBreadcrumb}
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
          {t.azBenchTitle}
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">{t.azBenchDesc}</p>
      </div>

      {/* Form */}
      <form
        onSubmit={startBench}
        className="border rounded-xl p-4 bg-card grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end"
      >
        <div>
          <label htmlFor="bench-zoo" className="text-xs text-muted-foreground block mb-1">{t.azBenchZoo}</label>
          <select
            id="bench-zoo"
            value={zoo}
            onChange={(e) => setZoo(e.target.value)}
            disabled={busy}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
          >
            {ZOO_CARD_KEYS.map((z) => (
              <option key={z.id} value={z.id}>
                {tkey(t, z.titleKey)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="bench-universe" className="text-xs text-muted-foreground block mb-1">{t.azBenchUniverse}</label>
          <select
            id="bench-universe"
            value={universe}
            onChange={(e) => setUniverse(e.target.value)}
            disabled={busy}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
          >
            {universeOptions.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="bench-period" className="text-xs text-muted-foreground block mb-1">{t.azBenchPeriod}</label>
          <input
            id="bench-period"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            disabled={busy}
            placeholder="2020-2025"
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
          />
        </div>
        <div>
          <label htmlFor="bench-top" className="text-xs text-muted-foreground block mb-1">{t.azBenchTop}</label>
          <input
            id="bench-top"
            type="number"
            min={1}
            max={500}
            value={Number.isFinite(top) ? top : ""}
            onChange={(e) =>
              setTop(e.target.value === "" ? 20 : Number(e.target.value))
            }
            disabled={busy}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
          />
        </div>
        <div className="flex gap-2">
          {busy ? (
            <>
              <button
                type="button"
                onClick={cancelBench}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-danger/30 text-danger text-sm font-medium hover:bg-danger/10 transition"
              >
                <Square className="h-3.5 w-3.5" aria-hidden="true" /> Cancel
              </button>
              <div className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary/50 text-primary-foreground text-sm font-medium">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> {t.azBenchRunning}
              </div>
            </>
          ) : (
            <button
              type="submit"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition"
            >
              <Play className="h-3.5 w-3.5" aria-hidden="true" /> {t.azRunBench}
            </button>
          )}
        </div>
        {formError && (
          <p
            className="sm:col-span-2 lg:col-span-5 text-xs text-down dark:text-down"
            role="alert"
          >
            {formError}
          </p>
        )}
      </form>

      {/* Progress */}
      {(status === "submitting" || status === "streaming") && (
        <ProgressPanel jobId={jobId} progress={progress} onCancel={cancelBench} />
      )}

      {/* Result */}
      {result && (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">{t.azBenchTitle}</h2>
            <button
              onClick={exportCsv}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border hover:bg-muted transition"
            >
              <Download className="h-3.5 w-3.5" /> Export CSV
            </button>
          </div>
          <ResultPanel result={result} />
        </>
      )}

      {/* History */}
      <div className="border-t pt-6">
        <button
          onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}
          className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <History className="h-4 w-4" />
          {t.azBenchHistory || "Benchmark History"}
          <span className="text-xs text-muted-foreground">({history.length})</span>
        </button>
        {showHistory && (
          <div className="mt-3">
            {historyLoading ? (
              <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-1" /> Loading...
              </div>
            ) : history.length === 0 ? (
              <div className="text-center py-8 text-xs text-muted-foreground">
                No saved benchmarks yet. Run a benchmark to see it here.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 pr-3">Zoo</th>
                      <th className="py-2 pr-3">Universe</th>
                      <th className="py-2 pr-3">Period</th>
                      <th className="py-2 pr-3 text-right">Alive</th>
                      <th className="py-2 pr-3 text-right">Rev</th>
                      <th className="py-2 pr-3 text-right">Dead</th>
                      <th className="py-2 pr-3 text-right">Time</th>
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.run_id} className="border-b last:border-0 hover:bg-muted/20">
                        <td className="py-2 pr-3 font-medium">{h.zoo}</td>
                        <td className="py-2 pr-3 text-muted-foreground">{tkey(t, `azUniverse_${h.universe}`)}</td>
                        <td className="py-2 pr-3 font-mono text-muted-foreground">{h.period}</td>
                        <td className="py-2 pr-3 text-right text-emerald-400 font-mono">{h.alive}</td>
                        <td className="py-2 pr-3 text-right text-amber-400 font-mono">{h.reversed}</td>
                        <td className="py-2 pr-3 text-right text-danger font-mono">{h.dead}</td>
                        <td className="py-2 pr-3 text-right font-mono text-muted-foreground">
                          {h.wall_seconds ? `${h.wall_seconds.toFixed(0)}s` : "—"}
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {h.created_at ? h.created_at.slice(0, 10) : "—"}
                        </td>
                        <td className="py-2">
                          <div className="flex gap-1">
                            <button
                              onClick={async () => {
                                try {
                                  const detail = await api.getBenchHistoryDetail(h.run_id);
                                  if (detail.run) {
                                    setResult({
                                      alive: detail.run.alive,
                                      reversed: detail.run.reversed,
                                      dead: detail.run.dead,
                                      n_alphas_tested: detail.run.n_alphas_tested,
                                      n_skipped: detail.run.n_skipped,
                                      top5_by_ir: detail.run.top5_by_ir,
                                      dead_examples: detail.run.dead_examples,
                                      by_theme: detail.run.by_theme,
                                      meta: detail.run.meta,
                                    });
                                    setStatus("done");
                                  }
                                } catch { /* ignore */ }
                              }}
                              className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
                              title="View"
                            >
                              <Play className="h-3 w-3" />
                            </button>
                            <button
                              onClick={async () => {
                                if (!confirm("Delete this benchmark?")) return;
                                try {
                                  await api.deleteBenchHistory(h.run_id);
                                  loadHistory();
                                } catch { /* ignore */ }
                              }}
                              className="p-1 text-muted-foreground hover:text-danger rounded transition-colors"
                              title="Delete"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ProgressPanel({
  jobId,
  progress,
  onCancel,
}: {
  jobId: string | null;
  progress: BenchProgress | null;
  onCancel?: () => void;
}) {
  const { t } = useI18n();
  const pct = progress && progress.n_total > 0
    ? Math.min(100, Math.round((progress.n_done / progress.n_total) * 100))
    : 0;
  return (
    <div className="border rounded-xl p-4 bg-card space-y-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          {jobId ? t.azBenchJob.replace("{id}", jobId.slice(0, 12)) : t.azBenchSubmitting}
        </span>
        <div className="flex items-center gap-2">
          {progress && (
            <span className="font-mono tabular-nums">
              {progress.n_done} / {progress.n_total}
            </span>
          )}
          {onCancel && (
            <button
              onClick={onCancel}
              className="px-2 py-0.5 text-[10px] rounded border border-danger/30 text-danger hover:bg-danger/10 transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      {progress?.current_alpha_id && (
        <p className="text-xs text-muted-foreground font-mono truncate">
          {t.azBenchComputing.replace("{id}", progress.current_alpha_id)}
        </p>
      )}
    </div>
  );
}

function ResultPanel({ result }: { result: AlphaBenchResult }) {
  const { t } = useI18n();
  const { dark } = useDarkMode();
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    const theme = getChartTheme();
    const chart = echarts.init(chartRef.current);
    const themes = Object.keys(result.by_theme || {}).sort().map(k => translateTheme(t, k));
    const aliveSeries = themes.map((k) => result.by_theme?.[k]?.alive ?? 0);
    const reversedSeries = themes.map((k) => result.by_theme?.[k]?.reversed ?? 0);
    const deadSeries = themes.map((k) => result.by_theme?.[k]?.dead ?? 0);

    chart.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: {
        data: [t.azBenchAlive, t.azBenchReversed, t.azBenchDead],
        textStyle: { color: theme.textColor, fontSize: 11 },
        right: 8,
        top: 4,
      },
      grid: { left: 8, right: 8, top: 32, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: themes,
        axisLine: { lineStyle: { color: theme.axisColor } },
        axisLabel: { color: theme.textColor, fontSize: 10, rotate: themes.length > 6 ? 30 : 0 },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: theme.gridColor } },
        axisLabel: { color: theme.textColor, fontSize: 10 },
      },
      series: [
        { name: t.azBenchAlive, type: "bar", stack: "n", data: aliveSeries, itemStyle: { color: theme.upColor } },
        { name: t.azBenchReversed, type: "bar", stack: "n", data: reversedSeries, itemStyle: { color: theme.warningColor } },
        { name: t.azBenchDead, type: "bar", stack: "n", data: deadSeries, itemStyle: { color: theme.downColor } },
      ],
    });

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartRef.current);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [result, dark, t]);

  const totals = [
    { label: t.azBenchAlive, value: result.alive, icon: CheckCircle2, tone: "text-up" },
    { label: t.azBenchReversed, value: result.reversed, icon: AlertTriangle, tone: "text-amber-600 dark:text-amber-400" },
    { label: t.azBenchDead, value: result.dead, icon: XCircle, tone: "text-down" },
    { label: t.azBenchSkipped, value: result.skipped ?? 0, icon: Loader2, tone: "text-muted-foreground" },
  ];

  return (
    <div className="space-y-4">
      {/* Survivorship bias warning */}
      {(result.meta && Boolean(result.meta.survivorship_bias)) && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-lg border border-amber-500/30 bg-amber-500/5 text-sm">
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-600 dark:text-amber-400">Survivorship Bias Warning</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              This universe uses current index constituents, not point-in-time historical membership.
              Stocks that left the index (due to delisting, mergers, or downgrades) are excluded,
              so IC statistics may be biased upward. Point-in-time data requires paid providers.
            </p>
          </div>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {totals.map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="border rounded-xl p-4 bg-card flex items-center gap-3">
            <Icon className={cn("h-5 w-5 shrink-0", tone)} aria-hidden="true" />
            <div>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-xl font-bold tabular-nums">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Top tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TopTable title={t.azBenchTopIR} rows={result.top5_by_ir || []} />
        <TopTable title={t.azBenchMostReversed} rows={(result.dead_examples || []).slice(0, 3)} />
      </div>

      {/* By-theme breakdown */}
      {result.by_theme && Object.keys(result.by_theme).length > 0 && (
        <div className="border rounded-xl p-4 bg-card">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            {t.azBenchByTheme}
          </h3>
          <div ref={chartRef} style={{ height: 240 }} />
        </div>
      )}
    </div>
  );
}

function TopTable({ title, rows }: { title: string; rows: AlphaBenchTopRow[] }) {
  const { t } = useI18n();
  return (
    <div className="border rounded-xl overflow-hidden bg-card">
      <div className="px-4 py-2.5 border-b bg-muted/40">
        <h3 className="text-sm font-medium">{title}</h3>
      </div>
      {rows.length === 0 ? (
        <div className="px-4 py-6 text-xs text-muted-foreground text-center">
          {t.azBenchNoRows}
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left px-4 py-2 text-xs text-muted-foreground font-medium">{t.azColId}</th>
              <th className="text-right px-4 py-2 text-xs text-muted-foreground font-medium">{t.azBenchMeanIC}</th>
              <th className="text-right px-4 py-2 text-xs text-muted-foreground font-medium">{t.azBenchIR}</th>
              <th className="text-left px-4 py-2 text-xs text-muted-foreground font-medium">{t.azColTheme}</th>
              <th className="text-left px-4 py-2 text-xs text-muted-foreground font-medium">{t.azBenchCategory}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b last:border-0 hover:bg-muted/20">
                <td className="px-4 py-2">
                  <Link
                    to={`/alpha-zoo/${encodeURIComponent(r.id)}`}
                    className="text-primary hover:underline font-mono text-xs"
                  >
                    {r.id}
                  </Link>
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-xs">{fmtNum(r.ic_mean)}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-xs">{fmtNum(r.ir)}</td>
                <td className="px-4 py-2 text-xs text-muted-foreground">{(r.theme || []).map(th => translateTheme(t, th)).join(", ") || "—"}</td>
                <td className="px-4 py-2 text-xs">
                  <CategoryBadge category={r.category} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function CategoryBadge({ category }: { category: AlphaBenchTopRow["category"] }) {
  const { t } = useI18n();
  const tone =
    category === "alive"
      ? "bg-up/10 text-up"
      : category === "reversed"
        ? "bg-amber-500/10 text-amber-700 dark:text-amber-300"
        : "bg-down/10 text-down";
  const labelKey = category === "alive" ? "azCategory_alive" : category === "reversed" ? "azCategory_reversed" : "azCategory_dead";
  return (
    <span className={cn("inline-block px-2 py-0.5 rounded-full text-[10px] font-medium", tone)}>
      {tkey(t, labelKey)}
    </span>
  );
}
