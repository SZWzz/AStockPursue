// frontend/lib/navigation.ts
import { LayoutDashboard, TrendingUp, ListOrdered, Briefcase, FileText,
  FlaskConical, Workflow, Bot, LineChart, Search, Building2, Settings,
  Activity, Clock, type LucideIcon } from 'lucide-react'

export interface NavGroup {
  key: string
  items: NavItem[]
}

export interface NavItem {
  label: string // i18n key prefix: `nav.${item.label}`
  href: string
  icon: LucideIcon
}

export const navGroups: NavGroup[] = [
  {
    key: 'main',
    items: [
      { label: 'dashboard', href: '/', icon: LayoutDashboard },
    ],
  },
  {
    key: 'trade',
    items: [
      { label: 'trading', href: '/trading', icon: TrendingUp },
      { label: 'orders', href: '/trading/orders', icon: ListOrdered },
      { label: 'positions', href: '/trading/positions', icon: Briefcase },
      { label: 'paperTrading', href: '/paper-trading', icon: FileText },
    ],
  },
  {
    key: 'research',
    items: [
      { label: 'backtest', href: '/backtest', icon: LineChart },
      { label: 'factors', href: '/factors', icon: FlaskConical },
      { label: 'workflow', href: '/workflow', icon: Workflow },
      { label: 'agent', href: '/agent', icon: Bot },
    ],
  },
  {
    key: 'market',
    items: [
      { label: 'marketOverview', href: '/market', icon: Activity },
      { label: 'screener', href: '/screener', icon: Search },
      { label: 'broker', href: '/broker', icon: Building2 },
    ],
  },
  {
    key: 'system',
    items: [
      { label: 'settings', href: '/settings', icon: Settings },
      { label: 'systemStatus', href: '/system', icon: Activity },
      { label: 'scheduler', href: '/scheduler', icon: Clock },
    ],
  },
]
