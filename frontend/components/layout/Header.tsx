// frontend/components/layout/Header.tsx
'use client'

import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { LogOut, Bell } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { signOut } from '@/lib/auth-client'

function breadcrumbSegments(pathname: string): string[] {
  return pathname.split('/').filter(Boolean)
}

export function Header() {
  const pathname = usePathname()
  const t = useTranslations()
  const segments = breadcrumbSegments(pathname)

  return (
    <header
      className="fixed top-0 right-0 flex items-center justify-between px-[var(--page-padding)] bg-[var(--surface-1)] border-b border-[var(--border-subtle)] z-30"
      style={{ height: 'var(--header-height)', left: 'var(--sidebar-width)' }}
    >
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-[12px] text-[var(--foreground-secondary)]">
        {segments.length === 0 ? (
          <span className="text-[var(--foreground)]">{t('nav.dashboard')}</span>
        ) : (
          segments.map((seg, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-[var(--foreground-muted)]">/</span>}
              <span className={i === segments.length - 1 ? 'text-[var(--foreground)]' : ''}>
                {seg}
              </span>
            </span>
          ))
        )}
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-7 w-7">
          <Bell className="w-4 h-4" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger>
            <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full bg-[var(--surface-3)] text-[12px] font-semibold">
              U
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
