import { describe, it, expect } from 'vitest'
import { useOrderFormStore } from '@/stores'

describe('useOrderFormStore', () => {
  it('has default values', () => {
    const s = useOrderFormStore.getState()
    expect(s.side).toBe('buy')
    expect(s.orderType).toBe('limit')
    expect(s.symbol).toBe('')
    expect(s.price).toBe('')
    expect(s.quantity).toBe('')
  })

  it('sets symbol', () => {
    useOrderFormStore.getState().setSymbol('600519.SH')
    expect(useOrderFormStore.getState().symbol).toBe('600519.SH')
  })

  it('sets side', () => {
    useOrderFormStore.getState().setSide('sell')
    expect(useOrderFormStore.getState().side).toBe('sell')
  })

  it('sets order type', () => {
    useOrderFormStore.getState().setOrderType('market')
    expect(useOrderFormStore.getState().orderType).toBe('market')
  })

  it('sets price and quantity', () => {
    useOrderFormStore.getState().setPrice('12.50')
    useOrderFormStore.getState().setQuantity('100')
    expect(useOrderFormStore.getState().price).toBe('12.50')
    expect(useOrderFormStore.getState().quantity).toBe('100')
  })

  it('resets', () => {
    useOrderFormStore.getState().setSymbol('TEST')
    useOrderFormStore.getState().setPrice('99')
    useOrderFormStore.getState().reset()
    expect(useOrderFormStore.getState().symbol).toBe('')
    expect(useOrderFormStore.getState().price).toBe('')
    expect(useOrderFormStore.getState().side).toBe('buy')
  })
})
