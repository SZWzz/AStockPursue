// frontend/components/layout/Header.tsx
'use client'

import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { LogOut, Bell, Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { signOut } from '@/lib/auth-client'
import { useUIStore } from '@/stores'

function breadcrumbSegments(pathname: string): string[] {
  return pathname.split('/').filter(Boolean)
}

export function Header() {
  const pathname = usePathname()
  const t = useTranslations()
  const segments = breadcrumbSegments(pathname)
  const toggleSidebar = useUIStore((s) => s.toggleSidebar)

  return (
    <header
      className="fixed top-0 right-0 flex items-center justify-between px-6 bg-[var(--background)] border-b border-[var(--border-subtle)] z-30 left-0 lg:left-[var(--sidebar-width)]"
      style={{ height: 'var(--header-height)' }}
    >
      {/* Left side: hamburger + breadcrumb */}
      <div className="flex items-center">
        <button
          className="lg:hidden mr-3 p-1 rounded hover:bg-[var(--surface-1)]"
          onClick={toggleSidebar}
          aria-label="Toggle menu"
        >
          <Menu className="w-5 h-5 text-[var(--foreground)]" />
        </button>

        <nav className="flex items-center gap-1 text-[14px] text-[var(--foreground-secondary)]" aria-label="Breadcrumb">
          {segments.length === 0 ? (
            <span className="text-[var(--foreground)]">{t('nav.dashboard')}</span>
          ) : (
            segments.map((seg, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && <span className="text-[var(--foreground-muted)]">/</span>}
                <span className={i === segments.length - 1 ? 'text-[var(--foreground)]' : ''} {...(i === segments.length - 1 ? { 'aria-current': 'location' as const } : {})}>
                  {seg}
                </span>
              </span>
            ))
          )}
        </nav>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-8 w-8 relative">
          <Bell className="w-[18px] h-[18px]" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--primary)]" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger>
            <Button variant="ghost" className="h-8 gap-2 px-2">
              <span className="w-8 h-8 rounded-full bg-[var(--surface-2)] flex items-center justify-center text-[14px] font-semibold text-[var(--foreground)]">
                U
              </span>
              <span className="text-[14px] text-[var(--foreground-secondary)] hidden sm:inline">{t('common.user')}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem onClick={() => signOut()} className="text-[var(--destructive)] cursor-pointer">
              <LogOut className="w-4 h-4 mr-2" />
              {t('common.logout')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
