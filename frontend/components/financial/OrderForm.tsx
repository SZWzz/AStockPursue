// frontend/components/financial/OrderForm.tsx
'use client'

import { useTranslations } from 'next-intl'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useOrderFormStore } from '@/stores'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export function OrderForm() {
  const t = useTranslations()
  const { symbol, side, orderType, price, quantity, setSymbol, setSide, setOrderType, setPrice, setQuantity, reset } = useOrderFormStore()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const res = await fetch('/api/trading/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol, side, type: orderType,
          price: parseFloat(price) || 0,
          quantity: parseFloat(quantity) || 0,
        }),
      })
      if (!res.ok) throw new Error('Order failed')
      toast.success('Order placed')
      reset()
    } catch (err: any) {
      toast.error(err.message || 'Order failed')
    }
  }

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-5">
      <div className="text-[14px] font-semibold text-[var(--foreground)] mb-4">{t('trading.submit')}</div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex mb-2">
          <button
            type="button"
            className="flex-1 h-10 rounded-l-[6px] text-[14px] font-semibold data-[active=true]:bg-[var(--up)] data-[active=true]:text-white data-[active=false]:bg-[var(--surface-1)] data-[active=false]:text-[var(--foreground-secondary)]"
            data-active={side === 'buy'}
            onClick={() => setSide('buy')}
          >
            {t('trading.buy')}
          </button>
          <button
            type="button"
            className="flex-1 h-10 rounded-r-[6px] text-[14px] font-semibold data-[active=true]:bg-[var(--down)] data-[active=true]:text-white data-[active=false]:bg-[var(--surface-1)] data-[active=false]:text-[var(--foreground-secondary)]"
            data-active={side === 'sell'}
            onClick={() => setSide('sell')}
          >
            {t('trading.sell')}
          </button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.symbol')}</label>
            <Input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} required className="h-10 text-[13px] bg-[var(--surface-1)] border-[var(--border)]" />
          </div>
          <div className="space-y-1">
            <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.orderType')}</label>
            <Select value={orderType} onValueChange={v => setOrderType(v as 'limit' | 'market')}>
              <SelectTrigger className="h-10 text-[13px] bg-[var(--surface-1)] border-[var(--border)]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="limit">{t('trading.limit')}</SelectItem>
                <SelectItem value="market">{t('trading.market')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.quantity')}</label>
            <Input value={quantity} onChange={e => setQuantity(e.target.value)} type="number" step="any" required className="h-10 text-[13px] bg-[var(--surface-1)] border-[var(--border)]" />
          </div>
        </div>
        {orderType === 'limit' && (
          <div className="space-y-1">
            <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.price')}</label>
            <Input value={price} onChange={e => setPrice(e.target.value)} type="number" step="any" required className="h-10 text-[13px] bg-[var(--surface-1)] border-[var(--border)]" />
          </div>
        )}
        <button
          type="submit"
          className={cn(
            'w-full h-11 rounded-[6px] text-[16px] font-semibold text-white',
            side === 'buy' ? 'bg-[var(--up)]' : 'bg-[var(--down)]'
          )}
        >
          {side === 'buy' ? t('trading.buy') : t('trading.sell')} {symbol}
        </button>
      </form>
    </div>
  )
}
