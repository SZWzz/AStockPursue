// frontend/components/financial/OrderForm.tsx
'use client'

import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useOrderFormStore } from '@/stores'
import { toast } from 'sonner'

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
          quantity: parseFloat(quantity)
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
    <Card className="bg-[var(--surface-2)] border-[var(--border-default)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-[13px]">{t('trading.submit')}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.symbol')}</label>
              <Input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} required className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.side')}</label>
              <Select value={side} onValueChange={v => setSide(v as 'buy' | 'sell')}>
                <SelectTrigger className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">{t('trading.buy')}</SelectItem>
                  <SelectItem value="sell">{t('trading.sell')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.orderType')}</label>
              <Select value={orderType} onValueChange={v => setOrderType(v as 'limit' | 'market')}>
                <SelectTrigger className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="limit">{t('trading.limit')}</SelectItem>
                  <SelectItem value="market">{t('trading.market')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.quantity')}</label>
              <Input value={quantity} onChange={e => setQuantity(e.target.value)} type="number" step="any" required className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
          </div>
          {orderType === 'limit' && (
            <div className="space-y-1">
              <label className="text-[11px] text-[var(--foreground-muted)]">{t('trading.price')}</label>
              <Input value={price} onChange={e => setPrice(e.target.value)} type="number" step="any" required className="h-8 text-[13px] bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
          )}
          <Button type="submit" className="w-full h-8 text-[13px] bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-[var(--background)]">
            {t('trading.submit')}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
