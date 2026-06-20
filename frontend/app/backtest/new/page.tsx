// frontend/app/backtest/new/page.tsx — Create backtest form
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export default function NewBacktestPage() {
  const t = useTranslations()
  const router = useRouter()

  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [frequency, setFrequency] = useState('daily')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          symbol,
          start_date: startDate,
          end_date: endDate,
          frequency,
          initial_capital: parseFloat(initialCapital),
        }),
      })
      if (res.ok) {
        const result = await res.json()
        const created = result.data || result
        if (created?.id) {
          router.push(`/backtest/${created.id}`)
          return
        }
      }
      const errData = await res.json().catch(() => ({}))
      setError((errData as any)?.error || (errData as any)?.message || t('common.error'))
    } catch (e) {
      setError(t('common.error'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SidebarLayout>
      <div className="max-w-lg mx-auto space-y-3">
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('backtest.new')}</h1>

        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-[13px] text-[var(--down)] bg-[var(--down)]/5 border border-[var(--down)]/20 rounded-[var(--radius-sm)] px-3 py-2">
                {error}
              </div>
            )}

            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">{t('backtest.strategy')}</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('backtest.strategy')}
                required
                className="w-full bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--foreground)] text-[13px]"
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">{t('trading.symbol')}</label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="000001.SZ"
                required
                className="w-full bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--foreground)] text-[13px]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">{t('backtest.startDate')}</label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                  className="w-full bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--foreground)] text-[13px]"
                />
              </div>
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">{t('backtest.endDate')}</label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                  className="w-full bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--foreground)] text-[13px]"
                />
              </div>
            </div>

            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">{t('market.daily')} / Hourly</label>
              <Select value={frequency} onValueChange={(v) => setFrequency(v ?? 'daily')}>
                <SelectTrigger className="w-full h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">{t('market.daily')}</SelectItem>
                  <SelectItem value="hourly">Hourly</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">{t('backtest.initialCapital')}</label>
              <Input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(e.target.value)}
                min="1000"
                step="any"
                required
                className="w-full bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--foreground)] text-[13px]"
              />
            </div>

            <div className="flex gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push('/backtest')}
                className="flex-1 h-8 text-[13px] border-[var(--border-default)] text-[var(--foreground-secondary)]"
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="submit"
                disabled={submitting}
                className="flex-1 h-8 text-[13px] bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
              >
                {submitting ? t('common.loading') : t('common.create')}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </SidebarLayout>
  )
}
