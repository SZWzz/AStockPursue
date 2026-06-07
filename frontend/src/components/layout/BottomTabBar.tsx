import { Link, useLocation } from "react-router-dom";
import { LayoutDashboard, FolderOpen, Bot, Settings, History } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

const MOBILE_NAV = [
  { to: "/", icon: LayoutDashboard, i18nKey: "dashboard" as const },
  { to: "/projects", icon: FolderOpen, i18nKey: "projects" as const },
  { to: "/agent", icon: Bot, i18nKey: "agent" as const },
  { to: "/backtest-history", icon: History, i18nKey: "backtestHistory" as const },
  { to: "/settings", icon: Settings, i18nKey: "settings" as const },
];

export function BottomTabBar() {
  const { pathname } = useLocation();
  const { t } = useI18n();

  const isActive = (to: string) => {
    if (to === "/") return pathname === "/" || pathname === "/dashboard";
    return pathname.startsWith(to);
  };

  return (
    <nav className="mobile-bottom-nav md:hidden">
      {MOBILE_NAV.map(({ to, icon: Icon, i18nKey }) => {
        const active = isActive(to);
        return (
          <Link key={to} to={to} className={cn(active && "active")}>
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span>{t[i18nKey]}</span>
          </Link>
        );
      })}
    </nav>
  );
}
