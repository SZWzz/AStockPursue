// frontend/app/backtest/new/page.tsx — Create backtest form (Coinbase theme)
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const FREQUENCIES = [
  { value: '1m',  label: '1min' },
  { value: '5m',  label: '5min' },
  { value: '15m', label: '15min' },
  { value: '30m', label: '30min' },
  { value: '1h',  label: '1h' },
  { value: '4h',  label: '4h' },
  { value: '1d',  label: 'Daily' },
  { value: '1w',  label: 'Weekly' },
]

interface FormErrors {
  name?: string
  symbol?: string
  startDate?: string
  endDate?: string
  initialCapital?: string
}

export default function NewBacktestPage() {
  const t = useTranslations()
  const router = useRouter()

  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [frequency, setFrequency] = useState('1d')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [formErrors, setFormErrors] = useState<FormErrors>({})

  const validate = (): boolean => {
    const errors: FormErrors = {}

    if (!name.trim()) {
      errors.name = t('backtest.nameRequired')
    }

    if (!symbol.trim()) {
      errors.symbol = t('backtest.symbolRequired')
    } else if (!/^\d{6}\.(SZ|SH)$|^[A-Za-z]{2,10}(\.[A-Za-z]+)?$/.test(symbol.trim().toUpperCase())) {
      errors.symbol = t('backtest.symbolFormat')
    }

    if (!startDate) {
      errors.startDate = t('backtest.startDateRequired')
    }

    if (!endDate) {
      errors.endDate = t('backtest.endDateRequired')
    } else if (startDate && endDate && endDate <= startDate) {
      errors.endDate = t('backtest.endDateAfterStart')
    }

    const capital = parseFloat(initialCapital)
    if (isNaN(capital) || capital <= 0) {
      errors.initialCapital = t('backtest.capitalPositive')
    }

    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!validate()) return

    setSubmitting(true)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          symbols: [symbol.trim().toUpperCase()],
          start_date: startDate,
          end_date: endDate,
          frequency,
          initial_cash: parseFloat(initialCapital),
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
      const errData = await res.json().catch(() => ({})) as Record<string, unknown>
      setError(String(errData?.error || errData?.message || t('common.error')))
    } catch {
      setError(t('common.error'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleBlur = (field: keyof FormErrors) => {
    setFormErrors((prev) => {
      const next = { ...prev }
      delete next[field]
      return next
    })
  }

  return (
    <SidebarLayout>
      <div className="max-w-lg mx-auto space-y-3">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('backtest.new')}</h1>

        <div className="bg-white border border-[var(--border)] rounded-[6px] p-6">
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {error && (
              <div className="text-[13px] text-[var(--down)] bg-[var(--down)]/5 border border-[var(--down)]/20 rounded-[var(--radius-sm)] px-3 py-2">
                {error}
              </div>
            )}

            {/* Strategy Name */}
            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">
                {t('backtest.strategy')}
              </label>
              <Input
                value={name}
                onChange={(e) => { setName(e.target.value); setFormErrors((p) => { const n = { ...p }; delete n.name; return n }) }}
                onBlur={() => handleBlur('name')}
                placeholder={t('backtest.namePlaceholder')}
                className={formErrors.name ? 'border-[var(--down)]' : ''}
              />
              {formErrors.name && (
                <p className="text-[11px] text-[var(--down)] mt-1">{formErrors.name}</p>
              )}
            </div>

            {/* Symbol */}
            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('trading.symbol')}</label>
              <Input
                value={symbol}
                onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setFormErrors((p) => { const n = { ...p }; delete n.symbol; return n }) }}
                onBlur={() => handleBlur('symbol')}
                placeholder="000001.SZ"
                className={formErrors.symbol ? 'border-[var(--down)]' : ''}
              />
              {formErrors.symbol && (
                <p className="text-[11px] text-[var(--down)] mt-1">{formErrors.symbol}</p>
              )}
            </div>

            {/* Date range */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.startDate')}</label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); setFormErrors((p) => { const n = { ...p }; delete n.startDate; return n }) }}
                  onBlur={() => handleBlur('startDate')}
                  className={formErrors.startDate ? 'border-[var(--down)]' : ''}
                />
                {formErrors.startDate && (
                  <p className="text-[11px] text-[var(--down)] mt-1">{formErrors.startDate}</p>
                )}
              </div>
              <div>
                <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.endDate')}</label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => { setEndDate(e.target.value); setFormErrors((p) => { const n = { ...p }; delete n.endDate; return n }) }}
                  onBlur={() => handleBlur('endDate')}
                  className={formErrors.endDate ? 'border-[var(--down)]' : ''}
                />
                {formErrors.endDate && (
                  <p className="text-[11px] text-[var(--down)] mt-1">{formErrors.endDate}</p>
                )}
              </div>
            </div>

            {/* Frequency */}
            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">
                {t('backtest.frequency')}
              </label>
              <Select value={frequency} onValueChange={(v) => setFrequency(v ?? '1d')}>
                <SelectTrigger className="w-full h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FREQUENCIES.map((f) => (
                    <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Initial Capital */}
            <div>
              <label className="block text-[14px] font-semibold text-[var(--foreground)] mb-1.5">{t('backtest.initialCapital')}</label>
              <Input
                type="number"
                value={initialCapital}
                onChange={(e) => { setInitialCapital(e.target.value); setFormErrors((p) => { const n = { ...p }; delete n.initialCapital; return n }) }}
                onBlur={() => handleBlur('initialCapital')}
                min="1000"
                step="any"
                className={formErrors.initialCapital ? 'border-[var(--down)]' : ''}
              />
              {formErrors.initialCapital && (
                <p className="text-[11px] text-[var(--down)] mt-1">{formErrors.initialCapital}</p>
              )}
            </div>

            {/* Action buttons */}
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
