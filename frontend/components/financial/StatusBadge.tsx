// frontend/components/financial/StatusBadge.tsx
import { cn } from '@/lib/utils'

type StatusVariant = 'running' | 'filled' | 'success' | 'cancelled' | 'error' | 'paused' | 'pending' | 'stopped'

const statusStyles: Record<StatusVariant, string> = {
  running:    'bg-[rgba(0,82,255,0.10)] text-[#0052FF] border-[rgba(0,82,255,0.20)]',
  filled:     'bg-[rgba(5,177,105,0.10)] text-[#05B169] border-[rgba(5,177,105,0.20)]',
  success:    'bg-[rgba(5,177,105,0.10)] text-[#05B169] border-[rgba(5,177,105,0.20)]',
  cancelled:  'bg-[rgba(207,32,47,0.10)] text-[#CF202F] border-[rgba(207,32,47,0.20)]',
  error:      'bg-[rgba(207,32,47,0.10)] text-[#CF202F] border-[rgba(207,32,47,0.20)]',
  paused:     'bg-[rgba(244,176,0,0.10)] text-[#F4B000] border-[rgba(244,176,0,0.20)]',
  pending:    'bg-[rgba(124,130,138,0.10)] text-[#5B616E] border-[rgba(124,130,138,0.20)]',
  stopped:    'bg-[rgba(124,130,138,0.10)] text-[#5B616E] border-[rgba(124,130,138,0.20)]',
}

interface StatusBadgeProps {
  status: StatusVariant
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center h-6 px-2 rounded-[4px] border text-[12px] font-medium',
      statusStyles[status],
      className
    )}>
      {label || status}
    </span>
  )
}
