// frontend/stores/orderFormStore.ts
import { create } from 'zustand'

interface OrderFormState {
  symbol: string
  side: 'buy' | 'sell'
  orderType: 'limit' | 'market'
  price: string
  quantity: string
  setSymbol: (s: string) => void
  setSide: (s: 'buy' | 'sell') => void
  setOrderType: (t: 'limit' | 'market') => void
  setPrice: (p: string) => void
  setQuantity: (q: string) => void
  reset: () => void
}

const initial = { symbol: '', side: 'buy' as const, orderType: 'limit' as const, price: '', quantity: '' }

export const useOrderFormStore = create<OrderFormState>()((set) => ({
  ...initial,
  setSymbol: (symbol) => set({ symbol }),
  setSide: (side) => set({ side }),
  setOrderType: (orderType) => set({ orderType }),
  setPrice: (price) => set({ price }),
  setQuantity: (quantity) => set({ quantity }),
  reset: () => set(initial),
}))
