// frontend/lib/navigation.ts
import { LayoutDashboard, TrendingUp, ListOrdered, Briefcase, FileText,
  FlaskConical, Workflow, Bot, LineChart, Search, Building2, Settings,
  Activity, Clock, Code2, Brain, Bell, Microscope,
  Gauge, Zap, ArrowLeftRight, TrendingDown, AlertTriangle, type LucideIcon } from 'lucide-react'

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
    key: 'discovery',
    items: [
      { label: 'marketOverview', href: '/market', icon: Activity },
      { label: 'screener', href: '/screener', icon: Search },
    ],
  },
  {
    key: 'strategy',
    items: [
      { label: 'strategyLab', href: '/strategy-lab', icon: Code2 },
      { label: 'workflow', href: '/workflow', icon: Workflow },
      { label: 'factors', href: '/factors', icon: FlaskConical },
    ],
  },
  {
    key: 'backtest',
    items: [
      { label: 'backtest', href: '/backtest', icon: LineChart },
      { label: 'optimization', href: '/optimization', icon: Gauge },
      { label: 'researchAnalysis', href: '/research', icon: Microscope },
    ],
  },
  {
    key: 'trading',
    items: [
      { label: 'paperTrading', href: '/paper-trading', icon: FileText },
      { label: 'liveTrading', href: '/live-trading', icon: TrendingUp },
      { label: 'orders', href: '/trading/orders', icon: ListOrdered },
      { label: 'positions', href: '/trading/positions', icon: Briefcase },
      { label: 'signals', href: '/signals', icon: Zap },
    ],
  },
  {
    key: 'monitor',
    items: [
      { label: 'dashboard', href: '/', icon: LayoutDashboard },
      { label: 'correlation', href: '/analysis/correlation', icon: ArrowLeftRight },
      { label: 'drawdown', href: '/analysis/drawdown', icon: TrendingDown },
      { label: 'stressTest', href: '/analysis/stress-test', icon: AlertTriangle },
      { label: 'notifications', href: '/notifications', icon: Bell },
      { label: 'scheduler', href: '/scheduler', icon: Clock },
    ],
  },
  {
    key: 'system',
    items: [
      { label: 'broker', href: '/broker', icon: Building2 },
      { label: 'mlModels', href: '/ml', icon: Brain },
      { label: 'agent', href: '/agent', icon: Bot },
      { label: 'settings', href: '/settings', icon: Settings },
      { label: 'systemStatus', href: '/system', icon: Activity },
    ],
  },
]
