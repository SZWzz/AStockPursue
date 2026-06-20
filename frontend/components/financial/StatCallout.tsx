// frontend/components/financial/StatCallout.tsx
import { cn } from '@/lib/utils'

interface StatCalloutProps {
  label: string
  value: string
  change?: string
  direction?: 'up' | 'down' | 'neutral'
  size?: 'lg' | 'md'
}

export function StatCallout({ label, value, change, direction, size = 'md' }: StatCalloutProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-[12px] font-semibold text-[var(--foreground-secondary)]">
        {label}
      </div>
      <div className={cn(
        'font-mono tabular-nums text-[var(--foreground)] tracking-[-1px]',
        size === 'lg' ? 'text-[52px] font-[300] leading-[1.0]' : 'text-[44px] font-[400] leading-[1.09]'
      )}>
        {value}
      </div>
      {change && (
        <div className={cn(
          'flex items-center gap-1 text-[14px] font-mono tabular-nums',
          direction === 'up' && 'text-[var(--up)]',
          direction === 'down' && 'text-[var(--down)]',
          (!direction || direction === 'neutral') && 'text-[var(--foreground-secondary)]'
        )}>
          <span>{direction === 'up' ? '▲' : direction === 'down' ? '▼' : ''}</span>
          <span>{change}</span>
        </div>
      )}
    </div>
  )
}
