// frontend/app/error.tsx
'use client'

import { Button } from '@/components/ui/button'

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-3 text-center max-w-sm">
        <div className="text-[var(--destructive)] text-sm font-semibold">Something went wrong</div>
        <p className="text-[12px] text-[var(--foreground-muted)]">{error.message}</p>
        <Button variant="outline" size="sm" onClick={reset} className="mt-2">
          Retry
        </Button>
      </div>
    </div>
  )
}
