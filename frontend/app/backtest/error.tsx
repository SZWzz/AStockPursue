'use client'

import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'

export default function BacktestError({ error, reset }: { error: Error; reset: () => void }) {
  const t = useTranslations()
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-3 text-center max-w-sm">
        <div className="text-[var(--destructive)] text-sm font-semibold">{t('backtest.name')}</div>
        <p className="text-[12px] text-[var(--foreground-muted)]">{error.message}</p>
        <Button variant="outline" size="sm" onClick={reset} className="mt-2">
          {t('common.retry')}
        </Button>
      </div>
    </div>
  )
}
