import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-[6px] bg-[var(--surface-3)]', className)}
      {...props}
    />
  )
}
