import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { BarChart3, Bot, Database, FolderOpen, LayoutDashboard, Menu, Search, ArrowLeft, Plus, Trash2, Pencil, MessageSquare, ChevronsLeft, ChevronsRight, Settings, LogIn, LogOut, User, Users, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { api, type SessionItem } from "@/lib/api";
import { useAgentStore } from "@/stores/agent";
import { useAuthStore } from "@/stores/auth";
import { ConnectionBanner } from "@/components/layout/ConnectionBanner";
import { PostLoginSetup } from "@/components/layout/PostLoginSetup";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { CommandPalette } from "@/components/layout/CommandPalette";

const MAIN_NAV_KEYS = [
  { to: "/", icon: LayoutDashboard, i18nKey: "dashboard" as const },
  { to: "/projects", icon: FolderOpen, i18nKey: "projects" as const },
  { to: "/agent", icon: Bot, i18nKey: "agent" as const },
  { to: "/data-sources", icon: Database, i18nKey: "dataSources" as const },
  { to: "/settings", icon: Settings, i18nKey: "settings" as const },
];

export function Layout() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const { t, lang, setLang } = useI18n();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const sseStatus = useAgentStore(s => s.sseStatus);
  const sseRetryAttempt = useAgentStore(s => s.sseRetryAttempt);
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeSessionId = searchParams.get("session");

  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", String(collapsed));
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

  const isActive = (to: string) => {
    if (to === "/") return pathname === "/" || pathname === "/dashboard";
    if (to === "/agent") return pathname.startsWith("/agent");
    return pathname.startsWith(to);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ConnectionBanner status={sseStatus} retryAttempt={sseRetryAttempt} />

      {/* Desktop Sidebar */}
      <aside className={cn(
        "hidden md:flex flex-col bg-surface-1 border-r border-border-subtle transition-all duration-200 shrink-0",
        collapsed ? "w-[52px]" : "w-[220px]"
      )}>
        {/* Logo */}
        <div className={cn(
          "flex items-center h-12 border-b border-border-subtle shrink-0",
          collapsed ? "justify-center px-2" : "px-3 gap-2"
        )}>
          <div className="h-6 w-6 rounded bg-primary flex items-center justify-center shrink-0">
            <span className="text-[10px] font-bold text-white">A</span>
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm tracking-tight">AStockPursue</span>
          )}
        </div>

        {/* Primary Nav */}
        <nav className={cn("py-1.5", collapsed ? "px-1.5" : "px-2")}>
          {MAIN_NAV_KEYS.map(({ to, icon: Icon, i18nKey }) => {
            const active = isActive(to);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "sidebar-nav-item",
                  collapsed ? "justify-center h-9 w-9 mx-auto rounded-md border-l-0" : "h-9 px-3 gap-2.5"
                )}
                title={collapsed ? t[i18nKey] : undefined}
              >
                <Icon className={cn("shrink-0", active ? "h-[18px] w-[18px]" : "h-4 w-4")} aria-hidden="true" />
                {!collapsed && <span>{t[i18nKey]}</span>}
              </Link>
            );
          })}
          {user?.role === "admin" && (
            <Link
              to="/admin/users"
              className={cn(
                "sidebar-nav-item",
                collapsed ? "justify-center h-9 w-9 mx-auto rounded-md border-l-0" : "h-9 px-3 gap-2.5"
              )}
              title={collapsed ? "Users" : undefined}
            >
              <Users className="h-4 w-4 shrink-0" />
              {!collapsed && <span>Users</span>}
            </Link>
          )}
        </nav>

        {/* Secondary Nav */}
        <div className={cn("py-1.5 border-t border-border-subtle", collapsed ? "px-1.5" : "px-2")}>
          {SECONDARY_NAV_KEYS.map(({ to, icon: Icon, i18nKey }) => {
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "sidebar-nav-item",
                  collapsed ? "justify-center h-9 w-9 mx-auto rounded-md border-l-0" : "h-9 px-3 gap-2.5"
                )}
                title={collapsed ? t[i18nKey] : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {!collapsed && <span>{t[i18nKey]}</span>}
              </Link>
            );
          })}
        </div>

        {/* Sessions — hidden when collapsed */}
        {!collapsed && (
          <div className="flex-1 overflow-hidden border-t border-border-subtle flex flex-col">
            <div className="flex items-center justify-between px-3 py-2">
              <span className="overline flex items-center gap-1.5">
                <MessageSquare className="h-3 w-3" />
                {t.sessions}
              </span>
              <Link to="/agent" className="p-1 rounded-md text-muted-foreground hover:text-foreground transition-colors" title={t.newChat}>
                <Plus className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="px-2 pb-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/50 pointer-events-none" />
                <input
                  type="text"
                  value={sessionFilter}
                  onChange={(e) => setSessionFilter(e.target.value)}
                  placeholder={t.filterSessions}
                  className="w-full pl-7 pr-2 py-1.5 text-xs rounded-md border border-border/50 bg-muted/20 focus:bg-surface-1 focus:border-primary/40 outline-none transition-colors placeholder:text-muted-foreground/40 font-mono"
                />
              </div>
            </div>

            <div className="px-2 pb-2 space-y-0.5 overflow-auto flex-1">
              {sessionsLoading ? (
                <div className="space-y-1.5 px-1 py-1">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-8 rounded-md skeleton-shimmer" />
                  ))}
                </div>
              ) : filteredSessions.length === 0 ? (
                <div className="empty-state py-6">
                  <MessageSquare className="empty-state-icon h-6 w-6" />
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
                        className="flex-1 min-w-0 px-2 py-1 rounded-md text-xs border border-primary bg-surface-1 outline-none font-mono"
                      />
                    ) : (
                      <Link
                        to={`/agent?session=${s.session_id}`}
                        className={cn(
                          "flex-1 min-w-0 pl-2 pr-14 py-1.5 rounded-r-md text-xs transition-all duration-150 truncate block border-l-2",
                          isActive
                            ? "bg-primary/[0.08] text-primary font-semibold border-l-primary"
                            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border-l-transparent"
                        )}
                        title={s.title || s.session_id}
                      >
                        <span className="flex items-center gap-1.5">
                          <span className={cn(
                            "h-1.5 w-1.5 rounded-full shrink-0",
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
                      <div className="absolute right-1.5 opacity-0 group-hover:opacity-100 flex items-center gap-0.5 transition-opacity duration-150">
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setRenameTarget(s.session_id); setRenameValue(s.title || ""); }}
                          className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
                          title={t.rename}
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDeleteTarget(s.session_id); }}
                          className="p-1 text-muted-foreground hover:text-danger rounded transition-colors"
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

        {/* Spacer when collapsed (pushes footer to bottom) */}
        {collapsed && <div className="flex-1" />}

        {/* Sidebar footer */}
        <div className={cn("border-t border-border-subtle", collapsed ? "p-1.5 flex flex-col items-center gap-1.5" : "p-2 space-y-1.5")}>
          {collapsed ? (
            <>
              {user ? (
                <button onClick={logout} className="p-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors" title={t.logout}>
                  <LogOut className="h-4 w-4" />
                </button>
              ) : (
                <Link to="/login" className="p-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors" title={t.login}>
                  <LogIn className="h-4 w-4" />
                </Link>
              )}
              <button onClick={() => setLang(lang === "zh" ? "en" : "zh")} className="p-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors text-[10px] font-bold" title="Language">
                {lang === "zh" ? "EN" : "中"}
              </button>
              <button onClick={() => setCollapsed(false)} className="p-1.5 text-muted-foreground hover:text-foreground rounded-md transition-colors" title="Expand">
                <ChevronsRight className="h-4 w-4" />
              </button>
            </>
          ) : (
            <>
              {user ? (
                <div className="flex items-center gap-2">
                  <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <User className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <span className="text-xs font-medium truncate flex-1">{user.username}</span>
                  <button onClick={logout} className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors" title={t.logout}>
                    <LogOut className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <Link to="/login" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors px-1">
                  <LogIn className="h-3.5 w-3.5" />
                  {t.login}
                </Link>
              )}
              <div className="flex items-center justify-between">
                <button onClick={() => setLang(lang === "zh" ? "en" : "zh")} className="px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground rounded transition-colors font-semibold">
                  {lang === "zh" ? "EN" : "中文"}
                </button>
                <button onClick={() => setCollapsed(true)} className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors" title="Collapse">
                  <ChevronsLeft className="h-4 w-4" />
                </button>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <>
          <div className="md:hidden fixed inset-0 z-50 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="md:hidden fixed inset-y-0 left-0 z-50 w-64 bg-surface-1 border-r border-border-subtle flex flex-col animate-slide-in-left">
            <div className="flex items-center justify-between h-12 px-3 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded bg-primary flex items-center justify-center">
                  <span className="text-[10px] font-bold text-white">A</span>
                </div>
                <span className="font-semibold text-sm">AStockPursue</span>
              </div>
              <button onClick={() => setMobileOpen(false)} className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors">
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex-1 py-2 px-2 space-y-0.5 overflow-auto">
              {[...MAIN_NAV_KEYS, ...SECONDARY_NAV_KEYS].map(({ to, icon: Icon, i18nKey }) => (
                <Link key={to} to={to} onClick={() => setMobileOpen(false)}
                  className="sidebar-nav-item h-10 px-3 gap-2.5 rounded-r-md">
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{t[i18nKey]}</span>
                </Link>
              ))}
              {user?.role === "admin" && (
                <Link to="/admin/users" onClick={() => setMobileOpen(false)}
                  className="sidebar-nav-item h-10 px-3 gap-2.5 rounded-r-md">
                  <Users className="h-4 w-4 shrink-0" />
                  <span>Users</span>
                </Link>
              )}
            </nav>
            <div className="p-3 border-t border-border-subtle flex items-center gap-2">
              {user ? (
                <>
                  <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs font-bold">
                    {(user.username || "U")[0].toUpperCase()}
                  </div>
                  <span className="text-xs flex-1">{user.username}</span>
                  <button onClick={() => { logout(); setMobileOpen(false); }} className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors">
                    <LogOut className="h-4 w-4" />
                  </button>
                </>
              ) : (
                <Link to="/login" onClick={() => setMobileOpen(false)} className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
                  <LogIn className="h-4 w-4" />{t.login}
                </Link>
              )}
            </div>
          </aside>
        </>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top header bar */}
        <header className="h-12 shrink-0 border-b border-border-subtle flex items-center px-4 gap-3 bg-surface-1/50">
          {/* Mobile menu button */}
          <button
            className="md:hidden p-1.5 -ml-1 text-muted-foreground hover:text-foreground rounded transition-colors"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Back to workflow button */}
          {searchParams.get("returnTo") && (
            <Link
              to={searchParams.get("returnTo")!}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Back
            </Link>
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Right actions */}
          <div className="flex items-center gap-2">
            {/* Lang toggle */}
            <button
              onClick={() => setLang(lang === "zh" ? "en" : "zh")}
              className="px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground rounded transition-colors font-semibold"
            >
              {lang === "zh" ? "EN" : "中"}
            </button>

            {/* SSE status indicator */}
            {sseStatus && (
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  sseStatus === "connected" ? "bg-success" :
                  sseStatus === "reconnecting" ? "bg-warning animate-pulse" :
                  "bg-danger"
                )}
                title={`SSE: ${sseStatus}`}
              />
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto bg-background">
          <Outlet />
        </main>

        {/* Mobile bottom tab bar */}
        <BottomTabBar />
      </div>

      {/* Post-login LLM setup prompt */}
      <PostLoginSetup />

      {/* Command palette (Cmd+K) */}
      <CommandPalette />
    </div>
  );
}
