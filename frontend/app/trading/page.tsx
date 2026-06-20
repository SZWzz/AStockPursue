// frontend/app/trading/page.tsx — Real-time trading panel
'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { SymbolSearch } from '@/components/financial/SymbolSearch'
import { OrderForm } from '@/components/financial/OrderForm'
import { CandlestickChart } from '@/components/financial/CandlestickChart'
import { OrderBook } from '@/components/financial/OrderBook'
import { PositionTable } from '@/components/financial/PositionTable'
import { useKlines } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useOrderFormStore } from '@/stores'
import { wsClient } from '@/lib/ws'

interface Level {
  price: number
  quantity: number
}

export default function TradingPage() {
  const t = useTranslations()
  useWebSocket()

  const [symbol, setSymbol] = useState('000001.SZ')
  const [orderBook, setOrderBook] = useState<{ bids: Level[]; asks: Level[] }>({ bids: [], asks: [] })
  const { data: klineData } = useKlines(symbol, 'daily')
  const setOrderFormSymbol = useOrderFormStore((s) => s.setSymbol)

  // Sync selected symbol into the OrderForm zustand store
  useEffect(() => {
    setOrderFormSymbol(symbol)
  }, [symbol, setOrderFormSymbol])

  // Listen for order book depth updates via WebSocket ticker feed
  useEffect(() => {
    const unsub = wsClient.on('ticker', (_channel, data) => {
      if (data?.symbol === symbol && (data?.bids || data?.asks)) {
        setOrderBook({
          bids: (data.bids || []) as Level[],
          asks: (data.asks || []) as Level[],
        })
      }
    })
    return unsub
  }, [symbol])

  const handleSymbolSelect = (s: string) => {
    setSymbol(s)
  }

  const bars = klineData?.bars || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.trading')}</h1>
          <SymbolSearch onSelect={handleSymbolSelect} />
        </div>

        {/* 12-column grid: OrderForm | Chart | OrderBook */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          {/* Order Form — 3 cols */}
          <div className="col-span-3">
            <OrderForm />
          </div>

          {/* Candlestick Chart — 6 cols */}
          <div className="col-span-6">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{symbol}</h2>
              <CandlestickChart data={bars} />
            </div>
          </div>

          {/* Order Book — 3 cols */}
          <div className="col-span-3">
            <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('market.depth')}</h2>
              <OrderBook bids={orderBook.bids} asks={orderBook.asks} />
            </div>
          </div>
        </div>

        {/* Positions section below the grid */}
        <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-md)] p-[var(--card-padding)]">
          <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">{t('nav.positions')}</h2>
          <PositionTable />
        </div>
      </div>
    </SidebarLayout>
  )
}
