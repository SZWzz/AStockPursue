import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { BarChart3, BookOpen, Bot, ChevronDown, Database, GitCompare, LayoutDashboard, Menu, Moon, Newspaper, Search, Sun, Plus, Trash2, Pencil, MessageSquare, ChevronsLeft, ChevronsRight, Settings, Layers, FlaskConical, Target, TrendingUp, LogIn, LogOut, User, Users, X, Microscope, Filter, PieChart, Clock, Store, CircleDollarSign, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useDarkMode } from "@/hooks/useDarkMode";
import { api, type SessionItem } from "@/lib/api";
import { useAgentStore } from "@/stores/agent";
import { useAuthStore } from "@/stores/auth";
import { ConnectionBanner } from "@/components/layout/ConnectionBanner";
import { PostLoginSetup } from "@/components/layout/PostLoginSetup";

const APP_VERSION = "v2026.6.4";

const MAIN_NAV = [
  { to: "/projects", icon: LayoutDashboard, label: "Projects" },
  { to: "/agent", icon: Bot, label: "Agent" },
  { to: "/data-sources", icon: Database, label: "Data Sources" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Layout() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const { t, lang, setLang } = useI18n();
  const { dark, toggle } = useDarkMode();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const sseStatus = useAgentStore(s => s.sseStatus);
  const sseRetryAttempt = useAgentStore(s => s.sseRetryAttempt);
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("qa-sidebar") === "collapsed");
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeSessionId = searchParams.get("session");

  useEffect(() => {
    localStorage.setItem("qa-sidebar", collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  const loadSessions = () => {
    api.listSessions()
      .then((list) => setSessions(Array.isArray(list) ? list : []))
      .catch(() => {})
      .finally(() => setSessionsLoading(false));
  };

  const isAgentPage = pathname === "/agent";
  useEffect(() => { loadSessions(); }, [isAgentPage, activeSessionId]);

  const [sessionFilter, setSessionFilter] = useState("");
  const filteredSessions = useMemo(() => {
    if (!sessionFilter.trim()) return sessions;
    const q = sessionFilter.toLowerCase();
    return sessions.filter(s => (s.title || s.session_id).toLowerCase().includes(q));
  }, [sessions, sessionFilter]);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const deleteSession = async (sid: string) => {
    try {
      await api.deleteSession(sid);
      setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    } catch { /* ignore */ }
    setDeleteTarget(null);
  };

  const renameSession = async (sid: string) => {
    if (!renameValue.trim()) { setRenameTarget(null); return; }
    try {
      await api.renameSession(sid, renameValue.trim());
      setSessions((prev) => prev.map((s) => s.session_id === sid ? { ...s, title: renameValue.trim() } : s));
    } catch { /* ignore */ }
    setRenameTarget(null);
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className={cn(
        "flex-col shrink-0 transition-all duration-300 border-r border-border/60 bg-surface-1",
        mobileOpen
          ? "fixed inset-y-0 left-0 z-50 flex w-64 overflow-auto shadow-lg"
          : cn("hidden md:flex", collapsed ? "md:w-14" : "md:w-64")
      )} onClick={() => setMobileOpen(false)}>
        {/* Brand */}
        <Link to="/" className={cn(
          "flex items-center font-bold tracking-tight border-b border-border/40",
          collapsed ? "h-12 justify-center" : "h-12 gap-2.5 px-4"
        )}>
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center shrink-0 shadow-sm shadow-primary/20">
            <BarChart3 className="h-4.5 w-4.5 text-primary-foreground" />
          </div>
          {!collapsed && <span className="text-base tracking-[-0.01em]">AStockPursue</span>}
        </Link>

        {/* Mobile close button */}
        <button
          className="md:hidden absolute top-3 right-3 p-1.5 rounded-lg hover:bg-muted transition-colors"
          onClick={() => setMobileOpen(false)}
          aria-label="Close menu"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Nav */}
        <nav className={cn("py-2", collapsed ? "px-2" : "px-0")}>
          {MAIN_NAV.map(({ to, icon: Icon, label }) => {
            const active = to === "/projects" ? pathname.startsWith("/projects") : to === "/agent" ? pathname.startsWith("/agent") : pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "flex items-center transition-all duration-200 mb-0.5 border-l-2",
                  collapsed ? "justify-center h-10 w-10 mx-auto rounded-lg border-l-0" : "gap-3 px-4 py-2.5 rounded-r-lg",
                  active
                    ? "bg-primary/[0.08] text-primary font-semibold border-l-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60 border-l-transparent"
                )}
                title={collapsed ? label : undefined}
              >
                <Icon className={cn("shrink-0", active ? "h-[18px] w-[18px]" : "h-4 w-4")} aria-hidden="true" />
                {!collapsed && <span className="text-sm">{label}</span>}
              </Link>
            );
          })}
          {user?.role === "admin" && (
            <Link
              to="/admin/users"
              className={cn(
                "flex items-center transition-all duration-200 border-l-2",
                collapsed ? "justify-center h-10 w-10 mx-auto rounded-lg border-l-0" : "gap-3 px-4 py-2.5 rounded-r-lg",
                pathname.startsWith("/admin")
                  ? "bg-primary/[0.08] text-primary font-semibold border-l-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/60 border-l-transparent"
              )}
              title={collapsed ? t.usersLabel : undefined}
            >
              <Users className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="text-sm">{t.usersLabel}</span>}
            </Link>
          )}
        </nav>

        {/* Sessions — hidden when collapsed */}
        {!collapsed && (
          <div className="flex-1 overflow-hidden border-t border-border/40 flex flex-col">
            <div className="flex items-center justify-between px-4 py-2.5">
              <span className="overline flex items-center gap-1.5">
                <MessageSquare className="h-3 w-3" />
                {t.sessions}
              </span>
              <Link
                to="/agent"
                className="btn-ghost p-1 rounded-md"
                title={t.newChat}
              >
                <Plus className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="px-3 pb-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60 pointer-events-none" />
                <input
                  type="text"
                  value={sessionFilter}
                  onChange={(e) => setSessionFilter(e.target.value)}
                  placeholder={t.filterSessions}
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-border/60 bg-muted/30 focus:bg-background focus:border-primary/50 outline-none transition-colors placeholder:text-muted-foreground/50"
                />
              </div>
            </div>

            <div className="px-3 pb-3 space-y-0.5 overflow-auto flex-1">
              {sessionsLoading ? (
                <div className="space-y-1.5 px-1 py-1">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-8 rounded-lg skeleton-shimmer" />
                  ))}
                </div>
              ) : filteredSessions.length === 0 ? (
                <div className="empty-state py-8">
                  <MessageSquare className="empty-state-icon h-8 w-8" />
                  <p className="empty-state-text">{sessionFilter.trim() ? (lang === "zh" ? "无匹配会话" : "No matching sessions") : t.noSessions}</p>
                </div>
              ) : null}
              {filteredSessions.map((s) => {
                const isActive = s.session_id === activeSessionId;
                const isDeleting = deleteTarget === s.session_id;
                const isRenaming = renameTarget === s.session_id;
                return (
                  <div key={s.session_id} className="group relative flex items-center">
                    {isRenaming ? (
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") renameSession(s.session_id); if (e.key === "Escape") setRenameTarget(null); }}
                        onBlur={() => renameSession(s.session_id)}
                        className="flex-1 min-w-0 px-3 py-1.5 rounded-lg text-sm border border-primary bg-background outline-none"
                      />
                    ) : (
                      <Link
                        to={`/agent?session=${s.session_id}`}
                        className={cn(
                          "flex-1 min-w-0 pl-3 pr-16 py-2 rounded-r-lg text-sm transition-all duration-200 truncate block border-l-2",
                          isActive
                            ? "bg-primary/[0.08] text-primary font-semibold border-l-primary"
                            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border-l-transparent"
                        )}
                        title={s.title || s.session_id}
                      >
                        <span className="flex items-center gap-2">
                          <span className={cn(
                            "h-2 w-2 rounded-full shrink-0",
                            s.status === "failed" ? "bg-danger" : isActive ? "bg-warning" : "bg-success/60"
                          )} />
                          {s.title || `${t.unnamedSession} #${s.session_id.slice(0, 8)}`}
                        </span>
                      </Link>
                    )}
                    {!isRenaming && isDeleting ? (
                      <div className="absolute right-1 flex items-center gap-0.5 animate-fade-in">
                        <button onClick={() => deleteSession(s.session_id)} className="btn-sm btn-danger py-0.5 text-[10px]">{t.confirmDelete}</button>
                        <button onClick={() => setDeleteTarget(null)} className="btn-sm btn-ghost py-0.5 text-[10px]">{t.cancelDelete}</button>
                      </div>
                    ) : !isRenaming ? (
                      <div className="absolute right-1.5 opacity-0 group-hover:opacity-100 flex items-center gap-0.5 transition-all duration-150">
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setRenameTarget(s.session_id); setRenameValue(s.title || ""); }}
                          className="p-1 text-muted-foreground hover:text-foreground rounded-md transition-colors"
                          title={t.rename}
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDeleteTarget(s.session_id); }}
                          className="p-1 text-muted-foreground hover:text-danger rounded-md transition-colors"
                          title={t.deleteConfirm}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Spacer when collapsed */}
        {collapsed && <div className="flex-1" />}

        {/* Footer */}
        <div className={cn("border-t border-border/40", collapsed ? "p-1.5 flex flex-col items-center gap-1.5" : "p-3 space-y-2.5")}>
          {/* User section */}
          {collapsed ? (
            <Link to={user ? "#" : "/login"} className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg transition-colors" title={user ? user.username : t.login}>
              <User className="h-4 w-4" />
            </Link>
          ) : user ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <User className="h-3.5 w-3.5 text-primary" />
                </div>
                <span className="text-sm font-medium truncate">{user.username}</span>
              </div>
              <button onClick={logout} className="btn-ghost p-1.5 rounded-lg" title={t.logout}>
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <Link to="/login" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors px-1">
              <LogIn className="h-4 w-4" />
              Sign in
            </Link>
          )}

          {collapsed ? (
            <>
              <button onClick={toggle} className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg transition-colors" title={dark ? t.lightMode : t.darkMode}>
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              <button
                onClick={() => setLang(lang === "zh" ? "en" : "zh")}
                className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg transition-colors text-[11px] font-semibold"
                title={t.language}
              >
                {lang === "zh" ? "EN" : "中"}
              </button>
              <button onClick={() => setCollapsed(false)} className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg transition-colors" title={t.expand}>
                <ChevronsRight className="h-4 w-4" />
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <button onClick={toggle} className="btn-ghost px-2 py-1 rounded-lg text-xs">
                    {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                    <span>{dark ? t.lightMode : t.darkMode}</span>
                  </button>
                  <button
                    onClick={() => setLang(lang === "zh" ? "en" : "zh")}
                    className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground rounded-md transition-colors font-semibold"
                    title={t.language}
                  >
                    {lang === "zh" ? "EN" : "中文"}
                  </button>
                </div>
                <button onClick={() => setCollapsed(true)} className="btn-ghost p-1.5 rounded-lg" title={t.collapse}>
                  <ChevronsLeft className="h-4 w-4" />
                </button>
              </div>
              <p className="text-[10px] text-muted-foreground/40 font-medium">{APP_VERSION}</p>
            </>
          )}
        </div>
      </aside>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/50"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile hamburger */}
      <button
        className="md:hidden fixed top-4 left-4 z-30 p-2 rounded-lg bg-card border border-border shadow-sm hover:bg-muted transition-colors"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <ConnectionBanner status={sseStatus} retryAttempt={sseRetryAttempt} />
        <main className="flex-1 overflow-auto bg-background">
          <Outlet />
        </main>
      </div>

      {/* Post-login LLM setup prompt */}
      <PostLoginSetup />
    </div>
  );
}
