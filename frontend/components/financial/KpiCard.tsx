// frontend/components/financial/KpiCard.tsx
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

interface KpiCardProps {
  label: string
  value: string
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
}

export function KpiCard({ label, value, sub, trend }: KpiCardProps) {
  return (
    <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
      <div className="text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider mb-1">{label}</div>
      <div className={cn(
        'text-lg font-medium font-mono tabular-nums',
        trend === 'up' && 'text-[var(--up)]',
        trend === 'down' && 'text-[var(--down)]',
        (!trend || trend === 'neutral') && 'text-[var(--foreground)]'
      )}>
        {value}
      </div>
      {sub && <div className="text-[11px] text-[var(--foreground-secondary)] mt-0.5">{sub}</div>}
    </Card>
  )
}
