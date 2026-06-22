// frontend/app/trading/page.tsx — Real-time trading panel
'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { PriceTicker } from '@/components/financial/PriceTicker'
import { OrderForm } from '@/components/financial/OrderForm'
import { CandlestickChart } from '@/components/financial/CandlestickChart'
import { OrderBook } from '@/components/financial/OrderBook'
import { PositionTable } from '@/components/financial/PositionTable'
import { useKlines, useSettings } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useOrderFormStore } from '@/stores'
import { wsClient } from '@/lib/ws'
import { cn } from '@/lib/utils'
import { Search, ChevronDown } from 'lucide-react'

interface Level {
  price: number
  quantity: number
}

export default function TradingPage() {
  const t = useTranslations()
  useWebSocket()

  const [symbol, setSymbol] = useState('000001')
  const [symbolCatalog, setSymbolCatalog] = useState<{ market: string; symbols: string[] }[]>([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const searchInputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const [orderBook, setOrderBook] = useState<{ bids: Level[]; asks: Level[] }>({ bids: [], asks: [] })
  const { data: klineData } = useKlines(symbol, 'daily')
  const setOrderFormSymbol = useOrderFormStore((s) => s.setSymbol)
  const { data: settingsData } = useSettings()

  // T3: Use user's default_symbols from settings as initial symbol if available
  const defaultSymbol = useMemo(() => {
    const ds = (settingsData as any)?.default_symbols ||
              (settingsData as any)?.general?.default_symbols
    if (Array.isArray(ds) && ds.length) return ds[0]
    return '000001'
  }, [settingsData])

  // Fetch symbol catalog from API on mount
  useEffect(() => {
    fetch('/api/market/symbols')
      .then(r => r.json())
      .then((data: { markets?: Record<string, string[]> }) => {
        if (data?.markets) {
          setSymbolCatalog(
            Object.entries(data.markets).map(([market, symbols]) => ({
              market,
              symbols: symbols || [],
            }))
          )
        }
      })
      .catch(() => {
        // fallback to empty array on error
        setSymbolCatalog([])
      })
  }, [])

  // Compute flat symbol list from catalog
  const ALL_SYMBOLS = useMemo(() => symbolCatalog.flatMap(g => g.symbols), [symbolCatalog])

  // Set default symbol from settings on mount
  useEffect(() => {
    if (settingsData) {
      setSymbol(defaultSymbol)
    }
  }, [defaultSymbol])

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

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filteredSymbols = searchQuery
    ? ALL_SYMBOLS.filter(s => s.toUpperCase().includes(searchQuery.toUpperCase()))
    : ALL_SYMBOLS

  const bars = klineData?.bars || []
  const latestBar = bars[bars.length - 1]
  const latestPrice = latestBar?.close
  const prevPrice = bars.length > 1 ? bars[bars.length - 2].close : latestPrice
  const change = latestPrice && prevPrice ? latestPrice - prevPrice : 0
  const changePct = prevPrice ? (change / prevPrice) * 100 : 0

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
            {t('nav.trading')}
          </h1>

          {/* T1: Symbol search autocomplete */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => { setSearchOpen(!searchOpen); setTimeout(() => searchInputRef.current?.focus(), 50) }}
              className="flex items-center gap-2 h-9 px-3 bg-white border border-[var(--border)] rounded-[6px] text-[13px] font-mono font-medium text-[var(--foreground)] hover:border-[var(--foreground-muted)] transition-colors"
            >
              <Search className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
              <span>{symbol}</span>
              <ChevronDown className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
            </button>

            {searchOpen && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-[var(--border)] rounded-[6px] shadow-lg z-50 overflow-hidden">
                <div className="p-2 border-b border-[var(--border)]">
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={t('common.search')}
                    className="w-full h-8 px-2 text-[12px] bg-[var(--surface-1)] border border-[var(--border)] rounded-[4px] outline-none focus:border-[var(--primary)]"
                  />
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {symbolCatalog.map((group) => {
                    const items = searchQuery
                      ? group.symbols.filter(s => s.toUpperCase().includes(searchQuery.toUpperCase()))
                      : group.symbols
                    if (!items.length) return null
                    return (
                      <div key={group.market}>
                        <div className="px-3 py-1.5 text-[10px] font-semibold text-[var(--foreground-muted)] uppercase">
                          {group.market}
                        </div>
                        {items.map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => { setSymbol(s); setSearchOpen(false); setSearchQuery('') }}
                            className={cn(
                              'w-full text-left px-3 py-1.5 text-[12px] font-mono hover:bg-[var(--surface-1)] transition-colors',
                              s === symbol && 'bg-[var(--surface-2)] text-[var(--primary)] font-semibold'
                            )}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* PriceTicker bar */}
        <PriceTicker
          symbol={symbol}
          price={latestPrice || 0}
          change={change}
          changePct={changePct}
          high={latestBar?.high || 0}
          low={latestBar?.low || 0}
        />

        {/* 12-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-[var(--grid-gap)]">
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
