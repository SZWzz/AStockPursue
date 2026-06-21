// frontend/components/layout/Sidebar.tsx
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { navGroups } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import { useTranslations } from 'next-intl'
import { useUIStore } from '@/stores'

export const APP_VERSION = 'v2026.6.21'

export function Sidebar() {
  const pathname = usePathname()
  const t = useTranslations()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <>
      {/* Mobile overlay backdrop */}
      {!sidebarCollapsed && (
        <div
          className="fixed inset-0 bg-black/20 z-30 lg:hidden"
          onClick={toggleSidebar}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 h-screen w-[var(--sidebar-width)] z-40 border-r border-[var(--border)] bg-[var(--background)] transition-transform duration-200 flex flex-col',
          'lg:translate-x-0',
          sidebarCollapsed ? '-translate-x-full' : 'translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-[var(--header-height)] shrink-0">
          <div className="w-6 h-6 rounded-[4px] bg-[var(--primary)] flex items-center justify-center text-white font-bold text-xs">
            A
          </div>
          <span className="font-semibold text-[16px] text-[var(--foreground)]">AStockPursue</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2" aria-label="Main navigation">
          {navGroups.map((group, gi) => (
            <div key={group.key} className={cn(gi > 0 && 'mt-4', 'px-4 py-1')}>
              <span className="text-[12px] font-semibold text-[var(--muted-foreground)]">
                {t(`nav.${group.key}`)}
              </span>
              {group.items.map((item) => {
                const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={() => { if (typeof window !== 'undefined' && window.innerWidth < 1024) toggleSidebar() }}
                    className={cn(
                      'flex items-center gap-3 px-4 h-9 text-[14px] transition-colors rounded-[6px] mx-2',
                      active
                        ? 'bg-[var(--primary-muted)] text-[var(--primary)] font-medium'
                        : 'text-[var(--foreground-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--surface-2)] font-normal'
                    )}
                  >
                    <item.icon className="w-[18px] h-[18px] shrink-0" />
                    <span className="truncate">{t(`nav.${item.label}`)}</span>
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div className="p-3 shrink-0">
          <div className="text-[12px] text-[var(--muted-foreground)] truncate">
            user@account
          </div>
          <div className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
            {APP_VERSION}
          </div>
        </div>
      </aside>
    </>
  )
}
