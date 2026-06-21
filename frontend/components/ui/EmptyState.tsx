'use client'

import Link from 'next/link'
import { cn } from '@/lib/utils'
import { FolderOpen } from 'lucide-react'

interface EmptyStateAction {
  label: string
  href: string
}

interface EmptyStateProps {
  title: string
  description: string
  action?: EmptyStateAction
  className?: string
  icon?: React.ReactNode
}

export function EmptyState({
  title,
  description,
  action,
  className,
  icon,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-4 text-center',
        className
      )}
    >
      <div className="mb-4 text-[var(--foreground-muted)]">
        {icon || <FolderOpen className="w-12 h-12 opacity-40" />}
      </div>
      <h3 className="text-[15px] font-medium text-[var(--foreground)] mb-1">
        {title}
      </h3>
      <p className="text-[13px] text-[var(--foreground-muted)] max-w-xs">
        {description}
      </p>
      {action && (
        <Link
          href={action.href}
          className="mt-4 inline-flex items-center gap-2 bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity"
        >
          {action.label}
        </Link>
      )}
    </div>
  )
}
