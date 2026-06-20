// frontend/components/layout/Sidebar.tsx
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { navGroups } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import { useTranslations } from 'next-intl'

export function Sidebar() {
  const pathname = usePathname()
  const t = useTranslations()

  return (
    <aside
      className="fixed left-0 top-0 h-screen flex flex-col bg-[var(--surface-1)] border-r border-[var(--border-subtle)] z-40"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-[var(--header-height)] border-b border-[var(--border-subtle)] shrink-0">
        <div className="w-6 h-6 rounded bg-[var(--primary)] flex items-center justify-center text-[var(--background)] font-bold text-xs">
          A
        </div>
        <span className="font-bold text-sm text-[var(--foreground)]">AStockPursue</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        {navGroups.map((group, gi) => (
          <div key={group.key} className={cn(gi > 0 && 'mt-3')}>
            <div className="px-4 py-1 text-[11px] font-semibold text-[var(--foreground-muted)] uppercase tracking-wider">
              {t(`nav.${group.key}`)}
            </div>
            {group.items.map((item) => {
              const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-4 h-8 text-[13px] transition-colors',
                    active
                      ? 'bg-[var(--primary-muted)] text-[var(--primary)] border-l-[3px] border-[var(--primary)]'
                      : 'text-[var(--foreground-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--surface-2)] border-l-[3px] border-transparent'
                  )}
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t(`nav.${item.label}`)}</span>
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-[var(--border-subtle)] shrink-0">
        <div className="text-[11px] text-[var(--foreground-muted)] truncate">
          user@account
        </div>
      </div>
    </aside>
  )
}
