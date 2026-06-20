// frontend/app/trading/page.tsx — Real-time trading panel
'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { PriceTicker } from '@/components/financial/PriceTicker'
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

  const bars = klineData?.bars || []

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('nav.trading')}
        </h1>

        {/* PriceTicker bar — new */}
        <PriceTicker
          symbol={symbol}
          price={12.50}
          change={0.32}
          changePct={2.63}
          high={12.65}
          low={12.10}
        />

        {/* 12-column grid */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-3">
            <OrderForm />
          </div>
          <div className="col-span-6">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{symbol}</h2>
              <CandlestickChart data={bars} />
            </div>
          </div>
          <div className="col-span-3">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('market.depth')}</h2>
              <OrderBook bids={orderBook.bids} asks={orderBook.asks} />
            </div>
          </div>
        </div>

        {/* Positions */}
        <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
          <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('nav.positions')}</h2>
          <PositionTable />
        </div>
      </div>
    </SidebarLayout>
  )
}
