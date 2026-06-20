// frontend/app/backtest/new/page.tsx — Create backtest form (Coinbase theme)
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
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
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('backtest.new')}</h1>

        <div className="bg-white border border-[var(--border)] rounded-[6px] p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-[13px] text-[var(--down)] bg-[var(--down)]/5 border border-[var(--down)]/20 rounded-[var(--radius-sm)] px-3 py-2">
                {error}
              </div>
            )}

            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.strategy')}</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('backtest.strategy')}
                required
              />
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('trading.symbol')}</label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="000001.SZ"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.startDate')}</label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.endDate')}</label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('market.daily')} / Hourly</label>
              <Select value={frequency} onValueChange={(v) => setFrequency(v ?? 'daily')}>
                <SelectTrigger className="w-full h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">{t('market.daily')}</SelectItem>
                  <SelectItem value="hourly">Hourly</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.initialCapital')}</label>
              <Input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(e.target.value)}
                min="1000"
                step="any"
                required
              />
            </div>

            <div className="flex gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push('/backtest')}
                className="flex-1"
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="submit"
                disabled={submitting}
                className="flex-1"
              >
                {submitting ? t('common.loading') : t('common.create')}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </SidebarLayout>
  )
}
