// frontend/components/financial/KpiCard.tsx
import { cn } from '@/lib/utils'
import type { KpiData } from '@/types'

export type { KpiData } from '@/types'

interface KpiCardProps {
  label: string
  value: string
  change?: string
  direction?: 'up' | 'down' | 'neutral'
}

export function KpiCard({ label, value, change, direction }: KpiCardProps) {
  return (
    <div className="bg-[var(--surface-1)] rounded-[6px] px-6 py-5">
      <div className="text-[12px] font-semibold text-[var(--foreground-secondary)] mb-2">
        {label}
      </div>
      <div className="text-[44px] font-[400] leading-[1.09] tracking-[-1px] font-mono tabular-nums text-[var(--foreground)]">
        {value}
      </div>
      {change && (
        <div className={cn(
          'flex items-center gap-1 mt-1.5 text-[14px] font-mono tabular-nums',
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
