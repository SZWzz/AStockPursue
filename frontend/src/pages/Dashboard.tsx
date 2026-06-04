import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { request } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  TrendingUp, Database, Newspaper, Microscope,
  Zap, Target, Activity, RefreshCw,
  LayoutDashboard, FolderOpen, Bot, Settings,
  Workflow, Play,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────

interface DashboardData {
  market?: {
    indices?: Array<{ name: string; code: string; price: number; change_pct: number }>;
    vix?: number;
    fear_greed?: { value: number; label: string };
  } | null;
  datasource?: {
    sources?: Array<{ name: string; markets: string[]; requires_auth: boolean; available: boolean }>;
    cache_hit_rate?: number;
    api_calls_today?: number;
  } | null;
  sentiment?: {
    overall_sentiment?: number;
    sentiment_label?: string;
    trend?: string;
    trending_topics?: Array<{ topic: string; count: number }>;
    recent_headlines?: string[];
  } | null;
  papertrading?: {
    strategies?: Array<{
      name: string; status: string;
      total_return_pct?: number; sharpe?: number;
      daily_pnl_pct?: number; max_drawdown_pct?: number;
      positions?: string[];
    }>;
    count?: number;
  } | null;
  pipeline?: {
    mining?: { active_gp_runs: number; active_llm_agents: number };
    candidates?: { pending_validation: number; pending_review: number; passed: number; redundant: number };
    zoo?: { total_factors: number; themes: number; alive: number; reversed: number; dead: number };
    theme_health?: Record<string, { count: number; mean_ic: number; trend: string }>;
  } | null;
  lab?: {
    recent_discoveries?: Array<{ alpha_id: string; formula: string; test_ic: number; status: string }>;
  } | null;
  activity?: {
    events?: Array<{ time: string; event: string }>;
  } | null;
}

// ── Main Dashboard ────────────────────────────────────────────────────

export function Dashboard() {
  const { t } = useI18n();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const json = await request<DashboardData>("/dashboard/overview");
      setData(json);
    } catch (e: any) {
      setError(e.message || (t as any).dashStale || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
        {(t as any).dashLoading || "Loading dashboard..."}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto p-6 gap-4 page-enter-stagger max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{(t as any).dashTitle || "Dashboard"}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">System overview & quick navigation</p>
        </div>
        <button onClick={fetchData} className="btn btn-ghost btn-sm" title={(t as any).dashRefresh || "Refresh"}>
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="message-bar warning rounded-lg text-sm">
          {(t as any).dashStale || "Data may be stale"}: {error}
        </div>
      )}

      {/* Row 1: Market + Data Source Health + Sentiment */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <MarketCard data={data?.market} t={t} />
        <DataSourceCard data={data?.datasource} t={t} />
        <SentimentCard data={data?.sentiment} t={t} />
      </div>

      {/* Row 2: Factor Pipeline (full width) */}
      <PipelineCard data={data?.pipeline} t={t} />

      {/* Row 3: Paper Trading + Factor Lab */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PaperTradingCard data={data?.papertrading} t={t} />
        <FactorLabCard data={data?.lab} t={t} />
      </div>

      {/* Row 4: Quick Navigation (sidebar-matched) */}
      <QuickNavCard t={t} />

      {/* Row 5: Recent Activity */}
      <ActivityCard data={data?.activity} t={t} />
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("section-card p-4 rounded-2xl", className)}>{children}</div>;
}

// ── Market Card ───────────────────────────────────────────────────────

function MarketCard({ data, t }: { data: DashboardData["market"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{(t as any).dashMarketOverview || "Market Overview"} —</p></Card>;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-blue-500" /> {(t as any).dashMarketOverview || "Market Overview"}
      </h3>
      <div className="space-y-2">
        {(data.indices || []).map((idx) => (
          <div key={idx.code} className="flex justify-between items-center text-sm">
            <span className="font-medium">{idx.name}</span>
            <span className="flex items-center gap-2">
              <span className="tabular-nums">{idx.price?.toLocaleString()}</span>
              <span className={cn("tabular-nums text-xs px-1.5 py-0.5 rounded-md font-medium",
                idx.change_pct >= 0
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                  : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400")}>
                {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct?.toFixed(1)}%
              </span>
            </span>
          </div>
        ))}
      </div>
      {data.fear_greed && (
        <div className="mt-3 pt-3 border-t border-border/50 text-sm flex justify-between">
          <span className="text-muted-foreground">{(t as any).dashFearGreed || "Fear & Greed"}</span>
          <span className="font-semibold">{data.fear_greed.value} ({data.fear_greed.label})</span>
        </div>
      )}
    </Card>
  );
}

// ── Data Source Card ──────────────────────────────────────────────────

function DataSourceCard({ data, t }: { data: DashboardData["datasource"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{(t as any).dashDataSourceHealth || "Data Sources"} —</p></Card>;
  const available = (data.sources || []).filter(s => s.available).length;
  const total = (data.sources || []).length;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Database className="w-4 h-4 text-emerald-500" /> {(t as any).dashDataSourceHealth || "Data Sources"}
      </h3>
      <div className="text-2xl font-bold tabular-nums mb-1">
        {available}<span className="text-base text-muted-foreground font-normal">/{total} healthy</span>
      </div>
      <div className="flex gap-1 flex-wrap mb-3">
        {(data.sources || []).slice(0, 10).map(s => (
          <span key={s.name} className={cn("text-xs px-1.5 py-0.5 rounded-full",
            s.available
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
              : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
          )}>{s.name}</span>
        ))}
      </div>
      <div className="text-xs text-muted-foreground space-y-1">
        <div>Cache hit: {data.cache_hit_rate != null ? `${(data.cache_hit_rate * 100).toFixed(0)}%` : "—"}</div>
        <div>API calls: {data.api_calls_today != null ? data.api_calls_today : "—"}</div>
      </div>
      <Link to="/data-sources" className="text-xs text-primary hover:underline mt-2 inline-block font-medium">
        Manage →
      </Link>
    </Card>
  );
}

// ── Sentiment Card ────────────────────────────────────────────────────

function SentimentCard({ data, t }: { data: DashboardData["sentiment"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{(t as any).dashMarketSentiment || "Sentiment"} —</p></Card>;
  const hasSentiment = data.overall_sentiment != null;
  const isPositive = hasSentiment && data.overall_sentiment! > 0.5;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Newspaper className="w-4 h-4 text-violet-500" /> {(t as any).dashMarketSentiment || "Sentiment"}
      </h3>
      <div className="flex items-center gap-2 mb-2">
        <span className={cn("text-2xl font-bold", hasSentiment ? (isPositive ? "text-emerald-600" : "text-red-600") : "text-muted-foreground")}>
          {hasSentiment ? (data.overall_sentiment!).toFixed(2) : "—"}
        </span>
        {hasSentiment && (
          <span className={cn("text-sm px-2 py-0.5 rounded-full font-medium",
            isPositive ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700")}>
            {data.sentiment_label || (isPositive ? "Bullish" : "Bearish")}
          </span>
        )}
        {data.trend === "rising" && <TrendingUp className="w-4 h-4 text-emerald-500" />}
      </div>
      <div className="space-y-1">
        {(data.trending_topics || []).slice(0, 3).map(tp => (
          <div key={tp.topic} className="flex justify-between text-xs">
            <span className="font-medium">#{tp.topic}</span>
            <span className="text-muted-foreground">{tp.count}</span>
          </div>
        ))}
      </div>
      {data.recent_headlines && data.recent_headlines.length > 0 && (
        <div className="mt-2 pt-2 border-t border-border/50 text-xs text-muted-foreground line-clamp-2">
          {data.recent_headlines[0]}
        </div>
      )}
    </Card>
  );
}

// ── Paper Trading Card ────────────────────────────────────────────────

function PaperTradingCard({ data, t }: { data: DashboardData["papertrading"]; t: any }) {
  if (!data || !data.strategies?.length) {
    return (
      <Card>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-amber-500" /> {(t as any).dashPaperTrading || "Paper Trading"}
        </h3>
        <p className="text-muted-foreground text-sm">{(t as any).dashNoActiveStrategies || "No active strategies"}</p>
        <Link to="/paper-trading" className="text-xs text-primary hover:underline mt-2 inline-block font-medium">Start →</Link>
      </Card>
    );
  }
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Target className="w-4 h-4 text-amber-500" /> {(t as any).dashPaperTrading || "Paper Trading"} ({data.count ?? data.strategies.length})
      </h3>
      <div className="space-y-3">
        {data.strategies.map(s => (
          <div key={s.name} className="border border-border/60 rounded-xl p-3 hover:bg-muted/30 transition-colors">
            <div className="flex justify-between items-center mb-1">
              <span className="font-medium text-sm">{s.name}</span>
              <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-medium",
                s.status === "running"
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30"
                  : "bg-muted text-muted-foreground")}>{s.status}</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-xs">
              <div><span className="text-muted-foreground">Return</span><br/><span className={cn("font-semibold", (s.total_return_pct ?? 0) >= 0 ? "text-emerald-600" : "text-red-600")}>{(s.total_return_pct ?? 0) >= 0 ? "+" : ""}{s.total_return_pct?.toFixed(1)}%</span></div>
              <div><span className="text-muted-foreground">Sharpe</span><br/><span className="font-semibold">{s.sharpe != null ? s.sharpe.toFixed(2) : "—"}</span></div>
              <div><span className="text-muted-foreground">Today</span><br/><span className={cn("font-semibold", (s.daily_pnl_pct ?? 0) >= 0 ? "text-emerald-600" : "text-red-600")}>{s.daily_pnl_pct != null ? `${(s.daily_pnl_pct ?? 0) >= 0 ? "+" : ""}${s.daily_pnl_pct.toFixed(2)}%` : "—"}</span></div>
              <div><span className="text-muted-foreground">MaxDD</span><br/><span className="font-semibold text-red-600">{s.max_drawdown_pct != null ? `${s.max_drawdown_pct.toFixed(1)}%` : "—"}</span></div>
            </div>
            {s.positions && s.positions.length > 0 && (
              <div className="mt-2 flex gap-1 flex-wrap">
                {s.positions.map(p => <span key={p} className="text-xs bg-muted px-1.5 py-0.5 rounded-md font-mono">{p}</span>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Pipeline Card ─────────────────────────────────────────────────────

function PipelineCard({ data, t }: { data: DashboardData["pipeline"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{(t as any).dashFactorPipeline || "Factor Pipeline"} —</p></Card>;
  const health = data.theme_health || {};
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Microscope className="w-4 h-4 text-purple-500" /> {(t as any).dashFactorPipeline || "Factor Pipeline"}
      </h3>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="text-center p-3 rounded-xl bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/30">
          <div className="text-xl font-bold text-purple-600">{data.mining?.active_gp_runs ?? 0}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{(t as any).dashGpRuns || "GP Runs"}</div>
        </div>
        <div className="text-center p-3 rounded-xl bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200 dark:border-cyan-800/30">
          <div className="text-xl font-bold text-cyan-600">{data.candidates?.pending_validation ?? 0}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{(t as any).dashPendingValidation || "Pending"}</div>
        </div>
        <div className="text-center p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/30">
          <div className="text-xl font-bold text-emerald-600">{data.zoo?.total_factors ?? 0}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{(t as any).dashZooFactors || "Zoo Factors"}</div>
        </div>
        <div className="text-center p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/30">
          <div className="text-xl font-bold text-amber-600">{data.zoo?.alive ?? 0}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{(t as any).dashProduction || "Production"}</div>
        </div>
      </div>
      {Object.keys(health).length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">{(t as any).dashThemeHealth || "Theme Health"}</div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(health).slice(0, 8).map(([theme, info]) => (
              <span key={theme} className={cn("text-xs px-2 py-1 rounded-full font-medium",
                info.trend === "rising" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30" :
                info.trend === "declining" ? "bg-red-100 text-red-700 dark:bg-red-900/30" : "bg-muted text-muted-foreground")}>
                {theme} IC:{info.mean_ic.toFixed(3)} x{info.count}
              </span>
            ))}
          </div>
        </div>
      )}
      <Link to="/factor-mining" className="text-xs text-primary hover:underline mt-3 inline-block font-medium">Open Factor Workbench →</Link>
    </Card>
  );
}

// ── Factor Lab Card ───────────────────────────────────────────────────

function FactorLabCard({ data, t }: { data: DashboardData["lab"]; t: any }) {
  if (!data || !data.recent_discoveries?.length) return null;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Zap className="w-4 h-4 text-cyan-500" /> {(t as any).dashRecentDiscoveries || "Recent Discoveries"}
      </h3>
      <div className="space-y-2">
        {data.recent_discoveries.map(d => (
          <div key={d.alpha_id} className="flex justify-between items-center text-xs">
            <span className="font-mono truncate max-w-[180px]" title={d.formula}>{d.formula}</span>
            <span className={cn("tabular-nums font-semibold",
              d.test_ic > 0.02 ? "text-emerald-600" : d.test_ic > 0.01 ? "text-amber-600" : "text-muted-foreground")}>
              IC: {d.test_ic.toFixed(3)}
            </span>
          </div>
        ))}
      </div>
      <Link to="/factor-mining" className="text-xs text-primary hover:underline mt-2 inline-block font-medium">Open Factor Workbench →</Link>
    </Card>
  );
}

// ── Quick Navigation (sidebar-matched only) ───────────────────────────

interface NavItem { to: string; icon: any; label: string; color: string; detail?: string }

function QuickNavCard({ t }: { t: any }) {
  const sections = [
    {
      label: "Navigation",
      items: [
        { to: "/", icon: LayoutDashboard, label: (t as any).dashTitle || "Dashboard", color: "text-primary" },
        { to: "/projects", icon: FolderOpen, label: "Projects", color: "text-blue-500" },
        { to: "/agent", icon: Bot, label: "Agent", color: "text-amber-500" },
        { to: "/data-sources", icon: Database, label: (t as any).dataSources || "Data Sources", color: "text-emerald-500" },
        { to: "/settings", icon: Settings, label: (t as any).settings || "Settings", color: "text-muted-foreground" },
      ] as NavItem[],
    },
    {
      label: "Workflow",
      items: [
        { to: "/projects", icon: Workflow, label: "Research Projects", color: "text-purple-500", detail: "Workflow pipelines" },
        { to: "/paper-trading", icon: Play, label: "Paper Trading", color: "text-amber-500", detail: "Live simulation" },
      ] as NavItem[],
    },
  ];

  return (
    <Card className="col-span-full">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map(sec => (
          <div key={sec.label}>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">{sec.label}</h3>
            <div className="space-y-1">
              {sec.items.map(item => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-muted/60 transition-colors group"
                >
                  <item.icon className={cn("w-4 h-4 shrink-0", item.color)} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium">{item.label}</span>
                    {item.detail && <span className="text-xs text-muted-foreground ml-2">{item.detail}</span>}
                  </div>
                  <span className="text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">→</span>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Activity Card ─────────────────────────────────────────────────────

function ActivityCard({ data, t }: { data: DashboardData["activity"]; t: any }) {
  if (!data || !data.events?.length) {
    return (
      <Card className="col-span-full">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-orange-500" /> {(t as any).dashRecentActivity || "Recent Activity"}
        </h3>
        <p className="text-xs text-muted-foreground">No recent events. Run a workflow or backtest to see activity here.</p>
      </Card>
    );
  }
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Activity className="w-4 h-4 text-orange-500" /> {(t as any).dashRecentActivity || "Recent Activity"}
      </h3>
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {data.events.slice(0, 15).map((e, i) => (
          <div key={i} className="flex gap-3 text-xs py-1.5 px-2 rounded-lg hover:bg-muted/30 transition-colors">
            <span className="text-muted-foreground tabular-nums w-10 shrink-0 font-mono">{e.time}</span>
            <span className="truncate">{e.event}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
