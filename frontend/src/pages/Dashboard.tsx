import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { request } from "@/lib/api";
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

// ── Card Components ──────────────────────────────────────────────────

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-xl border bg-card p-4 shadow-sm", className)}>
      {children}
    </div>
  );
}

function MarketOverview({ data }: { data: DashboardData["market"] }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">Market data unavailable</p></Card>;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-blue-500" /> Market Overview
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
          <span className="text-muted-foreground">Fear & Greed</span>
          <span className="font-semibold">{data.fear_greed.value} ({data.fear_greed.label})</span>
        </div>
      )}
    </Card>
  );
}

function DataSourceHealth({ data }: { data: DashboardData["datasource"] }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">Data source health unavailable</p></Card>;
  const available = (data.sources || []).filter(s => s.available).length;
  const total = (data.sources || []).length;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Database className="w-4 h-4 text-emerald-500" /> Data Sources
      </h3>
      <div className="text-2xl font-bold tabular-nums mb-1">
        {available}<span className="text-base text-muted-foreground font-normal">/{total} healthy</span>
      </div>
      <div className="flex gap-1 flex-wrap mb-3">
        {(data.sources || []).slice(0, 10).map(s => (
          <span key={s.name} className={cn(
            "text-xs px-1.5 py-0.5 rounded-full",
            s.available ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                        : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
          )}>{s.name}</span>
        ))}
      </div>
      <div className="text-xs text-muted-foreground space-y-1">
        <div>Cache hit: {(data.cache_hit_rate ?? 0) * 100}%</div>
        <div>API calls today: {data.api_calls_today ?? 0}</div>
      </div>
      <Link to="/data-sources" className="text-xs text-blue-500 hover:underline mt-2 inline-block">
        Manage data sources →
      </Link>
    </Card>
  );
}

function SentimentOverview({ data }: { data: DashboardData["sentiment"] }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">Sentiment data unavailable</p></Card>;
  const isPositive = (data.overall_sentiment ?? 0.5) > 0.5;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Newspaper className="w-4 h-4 text-violet-500" /> Market Sentiment
      </h3>
      <div className="flex items-center gap-2 mb-2">
        <span className={cn("text-2xl font-bold", isPositive ? "text-green-600" : "text-red-600")}>
          {(data.overall_sentiment ?? 0).toFixed(2)}
        </span>
        <span className={cn("text-sm px-2 py-0.5 rounded-full", isPositive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700")}>
          {data.sentiment_label || (isPositive ? "Bullish" : "Bearish")}
        </span>
        {data.trend === "rising" && <TrendingUp className="w-4 h-4 text-green-500" />}
      </div>
      <div className="space-y-1">
        {(data.trending_topics || []).slice(0, 3).map(t => (
          <div key={t.topic} className="flex justify-between text-xs">
            <span>#{t.topic}</span>
            <span className="text-muted-foreground">{t.count} items</span>
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

function PaperTradingRuntime({ data }: { data: DashboardData["papertrading"] }) {
  if (!data || !data.strategies?.length) {
    return (
      <Card>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-amber-500" /> Paper Trading
        </h3>
        <p className="text-muted-foreground text-sm">No active paper trading strategies</p>
        <Link to="/paper-trading" className="text-xs text-blue-500 hover:underline mt-2 inline-block">Start paper trading →</Link>
      </Card>
    );
  }
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Target className="w-4 h-4 text-amber-500" /> Paper Trading ({data.count ?? data.strategies.length} active)
      </h3>
      <div className="space-y-3">
        {data.strategies.map(s => (
          <div key={s.name} className="border rounded-lg p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="font-medium text-sm">{s.name}</span>
              <span className={cn("text-xs px-1.5 py-0.5 rounded-full", s.status === "running" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600")}>
                {s.status}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-xs">
              <div><span className="text-muted-foreground">Return</span><br/><span className={cn("font-semibold", (s.total_return_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600")}>{(s.total_return_pct ?? 0) >= 0 ? "+" : ""}{s.total_return_pct?.toFixed(1)}%</span></div>
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

function FactorPipeline({ data }: { data: DashboardData["pipeline"] }) {
  if (!data) return <Card><p className="text-muted-foreground text-sm">Factor pipeline data unavailable</p></Card>;
  const health = data.theme_health || {};
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Microscope className="w-4 h-4 text-purple-500" /> Factor Pipeline
      </h3>
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div className="text-center p-2 rounded-lg bg-purple-50 dark:bg-purple-900/20">
          <div className="text-lg font-bold">{data.mining?.active_gp_runs ?? 0}</div>
          <div className="text-xs text-muted-foreground">GP Runs</div>
        </div>
        <div className="text-center p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20">
          <div className="text-lg font-bold">{data.candidates?.pending_validation ?? 0}</div>
          <div className="text-xs text-muted-foreground">Pending Validation</div>
        </div>
        <div className="text-center p-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/20">
          <div className="text-lg font-bold">{data.zoo?.total_factors ?? 0}</div>
          <div className="text-xs text-muted-foreground">Zoo Factors</div>
        </div>
        <div className="text-center p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
          <div className="text-lg font-bold">{data.zoo?.alive ?? 0}</div>
          <div className="text-xs text-muted-foreground">Production</div>
        </div>
      </div>
      {Object.keys(health).length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Theme Health</div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(health).slice(0, 8).map(([theme, info]) => (
              <span key={theme} className={cn(
                "text-xs px-2 py-1 rounded-full",
                info.trend === "rising" ? "bg-emerald-100 text-emerald-700" :
                info.trend === "declining" ? "bg-red-100 text-red-700" :
                "bg-gray-100 text-gray-600"
              )}>
                {theme} IC:{info.mean_ic.toFixed(3)} ×{info.count}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function FactorLab({ data }: { data: DashboardData["lab"] }) {
  if (!data || !data.recent_discoveries?.length) return null;
  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-cyan-500" /> Recent Discoveries
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
        Open Factor Workbench →
      </Link>
    </Card>
  );
}

function RecentActivity({ data }: { data: DashboardData["activity"] }) {
  if (!data || !data.events?.length) return null;
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Activity className="w-4 h-4 text-orange-500" /> Recent Activity
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

function QuickActions() {
  const actions = [
    { to: "/factor-mining", icon: Microscope, label: "Mining", color: "text-purple-500" },
    { to: "/screener", icon: Search, label: "Screener", color: "text-blue-500" },
    { to: "/attribution", icon: PieChart, label: "Attribution", color: "text-cyan-500" },
    { to: "/agent", icon: Zap, label: "Agent", color: "text-amber-500" },
    { to: "/alpha-zoo", icon: Layers, label: "Zoo", color: "text-emerald-500" },
    { to: "/strategy-lab", icon: FlaskConical, label: "Strategies", color: "text-rose-500" },
    { to: "/trading", icon: BarChart3, label: "Trading", color: "text-indigo-500" },
    { to: "/sentiment", icon: Newspaper, label: "News", color: "text-violet-500" },
    { to: "/data-sources", icon: Database, label: "Data", color: "text-teal-500" },
  ];
  return (
    <Card className="col-span-full">
      <h3 className="text-sm font-semibold mb-3">Quick Actions</h3>
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

// ── Main Dashboard ────────────────────────────────────────────────────

export function Dashboard() {
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
      setError(e.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000); // refresh every 60s
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
        Loading dashboard…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">🏠 AStockPursue Dashboard</h1>
        <button onClick={fetchData} className="p-2 rounded-lg hover:bg-muted text-muted-foreground" title="Refresh">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="bg-amber-50 dark:bg-amber-900/20 text-amber-700 text-sm p-3 rounded-lg">
          Some data may be stale: {error}
        </div>
      )}

      {/* Row 1: Market + Data Source Health + Sentiment */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <MarketOverview data={data?.market} />
        <DataSourceHealth data={data?.datasource} />
        <SentimentOverview data={data?.sentiment} />
      </div>

      {/* Row 2: Factor Pipeline (full width) */}
      <FactorPipeline data={data?.pipeline} />

      {/* Row 3: Paper Trading + Factor Lab */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PaperTradingRuntime data={data?.papertrading} />
        <FactorLab data={data?.lab} />
      </div>

      {/* Row 4: Quick Actions */}
      <QuickActions />

      {/* Row 5: Recent Activity */}
      <RecentActivity data={data?.activity} />
    </div>
  );
}
