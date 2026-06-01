import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { request } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  TrendingUp, Database, Newspaper, Microscope,
  Zap, BarChart3, Target, Search,
  PieChart, FlaskConical, Layers, Activity, RefreshCw,
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
      const json = await request<DashboardData>("/dashboard/overview?user_id=1");
      setData(json);
    } catch (e: any) {
      setError(e.message || t.dashStale);
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
        {t.dashLoading}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">🏠 {t.dashTitle}</h1>
        <button onClick={fetchData} className="p-2 rounded-lg hover:bg-muted text-muted-foreground" title={t.dashRefresh}>
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="bg-amber-50 dark:bg-amber-900/20 text-amber-700 text-sm p-3 rounded-lg">
          {t.dashStale}: {error}
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

      {/* Row 4: Quick Actions */}
      <QuickActionsCard t={t} />

      {/* Row 5: Recent Activity */}
      <ActivityCard data={data?.activity} t={t} />
    </div>
  );
}

// ── Card Components (receive t as prop) ──────────────────────────────

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("rounded-xl border bg-card p-4 shadow-sm", className)}>{children}</div>;
}

function MarketCard({ data, t }: { data: DashboardData["market"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{t.dashMarketOverview} —</p></Card>;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-blue-500" /> {t.dashMarketOverview}
      </h3>
      <div className="space-y-2">
        {(data.indices || []).map((idx) => (
          <div key={idx.code} className="flex justify-between items-center text-sm">
            <span className="font-medium">{idx.name}</span>
            <span className="flex items-center gap-2">
              <span className="tabular-nums">{idx.price?.toLocaleString()}</span>
              <span className={cn("tabular-nums text-xs px-1.5 py-0.5 rounded", idx.change_pct >= 0 ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400")}>
                {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct?.toFixed(1)}%
              </span>
            </span>
          </div>
        ))}
      </div>
      {data.fear_greed && (
        <div className="mt-3 pt-3 border-t text-sm flex justify-between">
          <span className="text-muted-foreground">{t.dashFearGreed}</span>
          <span className="font-semibold">{data.fear_greed.value} ({data.fear_greed.label})</span>
        </div>
      )}
    </Card>
  );
}

function DataSourceCard({ data, t }: { data: DashboardData["datasource"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{t.dashDataSourceHealth} —</p></Card>;
  const available = (data.sources || []).filter(s => s.available).length;
  const total = (data.sources || []).length;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Database className="w-4 h-4 text-emerald-500" /> {t.dashDataSourceHealth}
      </h3>
      <div className="text-2xl font-bold tabular-nums mb-1">
        {available}<span className="text-base text-muted-foreground font-normal">/{total} {t.dashHealthy}</span>
      </div>
      <div className="flex gap-1 flex-wrap mb-3">
        {(data.sources || []).slice(0, 10).map(s => (
          <span key={s.name} className={cn("text-xs px-1.5 py-0.5 rounded-full",
            s.available ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                        : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
          )}>{s.name}</span>
        ))}
      </div>
      <div className="text-xs text-muted-foreground space-y-1">
        <div>{t.dashCacheHit}: {(data.cache_hit_rate ?? 0) * 100}%</div>
        <div>{t.dashApiCalls}: {data.api_calls_today ?? 0}</div>
      </div>
      <Link to="/data-sources" className="text-xs text-blue-500 hover:underline mt-2 inline-block">
        {t.dashManageDataSources}
      </Link>
    </Card>
  );
}

function SentimentCard({ data, t }: { data: DashboardData["sentiment"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{t.dashMarketSentiment} —</p></Card>;
  const isPositive = (data.overall_sentiment ?? 0.5) > 0.5;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Newspaper className="w-4 h-4 text-violet-500" /> {t.dashMarketSentiment}
      </h3>
      <div className="flex items-center gap-2 mb-2">
        <span className={cn("text-2xl font-bold", isPositive ? "text-green-600" : "text-red-600")}>
          {(data.overall_sentiment ?? 0).toFixed(2)}
        </span>
        <span className={cn("text-sm px-2 py-0.5 rounded-full", isPositive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700")}>
          {data.sentiment_label || (isPositive ? t.dashBullish : t.dashBearish)}
        </span>
        {data.trend === "rising" && <TrendingUp className="w-4 h-4 text-green-500" />}
      </div>
      <div className="space-y-1">
        {(data.trending_topics || []).slice(0, 3).map(tp => (
          <div key={tp.topic} className="flex justify-between text-xs">
            <span>#{tp.topic}</span>
            <span className="text-muted-foreground">{tp.count}</span>
          </div>
        ))}
      </div>
      {data.recent_headlines && data.recent_headlines.length > 0 && (
        <div className="mt-2 pt-2 border-t text-xs text-muted-foreground">
          {data.recent_headlines[0]}
        </div>
      )}
    </Card>
  );
}

function PaperTradingCard({ data, t }: { data: DashboardData["papertrading"]; t: any }) {
  if (!data || !data.strategies?.length) {
    return (
      <Card>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-amber-500" /> {t.dashPaperTrading}
        </h3>
        <p className="text-muted-foreground text-sm">{t.dashNoActiveStrategies}</p>
        <Link to="/paper-trading" className="text-xs text-blue-500 hover:underline mt-2 inline-block">{t.dashStartPaperTrading}</Link>
      </Card>
    );
  }
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Target className="w-4 h-4 text-amber-500" /> {t.dashPaperTrading} ({data.count ?? data.strategies.length})
      </h3>
      <div className="space-y-3">
        {data.strategies.map(s => (
          <div key={s.name} className="border rounded-lg p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="font-medium text-sm">{s.name}</span>
              <span className={cn("text-xs px-1.5 py-0.5 rounded-full", s.status === "running" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600")}>{s.status}</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-xs">
              <div><span className="text-muted-foreground">{t.ptReturn}</span><br/><span className={cn("font-semibold", (s.total_return_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600")}>{(s.total_return_pct ?? 0) >= 0 ? "+" : ""}{s.total_return_pct?.toFixed(1)}%</span></div>
              <div><span className="text-muted-foreground">Sharpe</span><br/><span className="font-semibold">{s.sharpe?.toFixed(2)}</span></div>
              <div><span className="text-muted-foreground">Today</span><br/><span className={cn("font-semibold", (s.daily_pnl_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600")}>{(s.daily_pnl_pct ?? 0) >= 0 ? "+" : ""}{s.daily_pnl_pct?.toFixed(2)}%</span></div>
              <div><span className="text-muted-foreground">MaxDD</span><br/><span className="font-semibold text-red-600">{s.max_drawdown_pct?.toFixed(1)}%</span></div>
            </div>
            {s.positions && s.positions.length > 0 && (
              <div className="mt-2 flex gap-1 flex-wrap">
                {s.positions.map(p => <span key={p} className="text-xs bg-muted px-1.5 py-0.5 rounded">{p}</span>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function PipelineCard({ data, t }: { data: DashboardData["pipeline"]; t: any }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">{t.dashFactorPipeline} —</p></Card>;
  const health = data.theme_health || {};
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Microscope className="w-4 h-4 text-purple-500" /> {t.dashFactorPipeline}
      </h3>
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div className="text-center p-2 rounded-lg bg-purple-50 dark:bg-purple-900/20">
          <div className="text-lg font-bold">{data.mining?.active_gp_runs ?? 0}</div>
          <div className="text-xs text-muted-foreground">{t.dashGpRuns}</div>
        </div>
        <div className="text-center p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20">
          <div className="text-lg font-bold">{data.candidates?.pending_validation ?? 0}</div>
          <div className="text-xs text-muted-foreground">{t.dashPendingValidation}</div>
        </div>
        <div className="text-center p-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/20">
          <div className="text-lg font-bold">{data.zoo?.total_factors ?? 0}</div>
          <div className="text-xs text-muted-foreground">{t.dashZooFactors}</div>
        </div>
        <div className="text-center p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
          <div className="text-lg font-bold">{data.zoo?.alive ?? 0}</div>
          <div className="text-xs text-muted-foreground">{t.dashProduction}</div>
        </div>
      </div>
      {Object.keys(health).length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">{t.dashThemeHealth}</div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(health).slice(0, 8).map(([theme, info]) => (
              <span key={theme} className={cn("text-xs px-2 py-1 rounded-full",
                info.trend === "rising" ? "bg-emerald-100 text-emerald-700" :
                info.trend === "declining" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600")}>
                {theme} IC:{info.mean_ic.toFixed(3)} ×{info.count}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function FactorLabCard({ data, t }: { data: DashboardData["lab"]; t: any }) {
  if (!data || !data.recent_discoveries?.length) return null;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-cyan-500" /> {t.dashRecentDiscoveries}
      </h3>
      <div className="space-y-2">
        {data.recent_discoveries.map(d => (
          <div key={d.alpha_id} className="flex justify-between items-center text-xs">
            <span className="font-mono truncate max-w-[180px]" title={d.formula}>{d.formula}</span>
            <span className={cn("tabular-nums font-semibold", d.test_ic > 0.02 ? "text-green-600" : d.test_ic > 0.01 ? "text-amber-600" : "text-muted-foreground")}>
              IC: {d.test_ic.toFixed(3)}
            </span>
          </div>
        ))}
      </div>
      <Link to="/factor-mining" className="text-xs text-blue-500 hover:underline mt-2 inline-block">
        {t.dashOpenFactorWorkbench}
      </Link>
    </Card>
  );
}

function QuickActionsCard({ t }: { t: any }) {
  const actions = [
    { to: "/factor-mining", icon: Microscope, label: t.dashMining, color: "text-purple-500" },
    { to: "/screener", icon: Search, label: t.dashScreener, color: "text-blue-500" },
    { to: "/attribution", icon: PieChart, label: t.dashAttribution, color: "text-cyan-500" },
    { to: "/agent", icon: Zap, label: t.dashAgent, color: "text-amber-500" },
    { to: "/alpha-zoo", icon: Layers, label: t.dashZoo, color: "text-emerald-500" },
    { to: "/strategy-lab", icon: FlaskConical, label: t.dashStrategies, color: "text-rose-500" },
    { to: "/trading", icon: BarChart3, label: t.dashTrading, color: "text-indigo-500" },
    { to: "/sentiment", icon: Newspaper, label: t.dashNews, color: "text-violet-500" },
    { to: "/data-sources", icon: Database, label: t.dashData, color: "text-teal-500" },
  ];
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3">{t.dashQuickActions}</h3>
      <div className="flex gap-2 flex-wrap">
        {actions.map(a => (
          <Link key={a.to} to={a.to}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border hover:bg-muted text-xs font-medium transition-colors">
            <a.icon className={cn("w-4 h-4", a.color)} />
            {a.label}
          </Link>
        ))}
      </div>
    </Card>
  );
}

function ActivityCard({ data, t }: { data: DashboardData["activity"]; t: any }) {
  if (!data || !data.events?.length) return null;
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Activity className="w-4 h-4 text-orange-500" /> {t.dashRecentActivity}
      </h3>
      <div className="space-y-1">
        {data.events.slice(0, 10).map((e, i) => (
          <div key={i} className="flex gap-2 text-xs">
            <span className="text-muted-foreground tabular-nums w-12 shrink-0">{e.time}</span>
            <span>{e.event}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
