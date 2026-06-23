import React from 'react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { renderHook, waitFor } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { usePositions } from '@/hooks/usePositions'
import { useOrders } from '@/hooks/useOrders'
import { useMarketData } from '@/hooks/useMarketData'
import { useKlines } from '@/hooks/useKlines'
import { useBacktest } from '@/hooks/useBacktest'
import type { Portfolio, Order } from '@/types'

// ── MSW server ────────────────────────────────────────────────
const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// ── SWR wrapper with isolated cache and explicit fetcher ──────
// jsdom does NOT expose window.fetch and Node.js fetch() requires
// absolute URLs. Detect relative URLs and prefix the target origin.
const BASE_URL = 'http://localhost:3000'
const resolveUrl = (url: string) =>
  url.startsWith('http') ? url : `${BASE_URL}${url}`

const testFetcher = async (url: string) => {
  const res = await globalThis.fetch(resolveUrl(url))
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig
    value={{
      provider: () => new Map(),
      dedupingInterval: 0,
      fetcher: testFetcher,
    }}
  >
    {children}
  </SWRConfig>
)

// ── Mock data ─────────────────────────────────────────────────
const mockPortfolio: Portfolio = {
  total_value: 100000,
  cash: 20000,
  market_value: 80000,
  unrealized_pnl: 5000,
  realized_pnl: 2000,
  positions: [
    {
      symbol: 'AAPL',
      side: 'long',
      size: 100,
      entry_price: 150,
      current_price: 200,
      market_value: 20000,
      pnl: 5000,
      pnl_pct: 33.33,
      realized_pnl: 0,
    },
    {
      symbol: 'TSLA',
      side: 'short',
      size: 50,
      entry_price: 300,
      current_price: 280,
      market_value: 14000,
      pnl: 1000,
      pnl_pct: 6.67,
      realized_pnl: 0,
    },
  ],
}

const emptyPortfolio: Portfolio = {
  total_value: 50000,
  cash: 50000,
  market_value: 0,
  unrealized_pnl: 0,
  realized_pnl: 0,
  positions: [],
}

const mockOrders: Order[] = [
  {
    id: 'order-1',
    symbol: 'AAPL',
    side: 'buy',
    type: 'limit',
    price: 150,
    quantity: 100,
    filled: 0,
    status: 'pending',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'order-2',
    symbol: 'TSLA',
    side: 'sell',
    type: 'market',
    price: 300,
    quantity: 50,
    filled: 50,
    status: 'filled',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
]

const emptyOrders: Order[] = []

const mockBars = [
  {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    price: 200,
    change: 5,
    change_pct: 2.56,
    volume: 1000000,
    high: 205,
    low: 195,
    open: 197,
    prev_close: 195,
  },
  {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    price: 198,
    change: 3,
    change_pct: 1.54,
    volume: 800000,
    high: 200,
    low: 196,
    open: 197,
    prev_close: 195,
  },
]

const emptyBars: typeof mockBars = []

const mockBacktestResult = {
  id: 'bt-1',
  symbol: 'AAPL',
  strategy: 'momentum',
  start_date: '2024-01-01',
  end_date: '2024-06-01',
  total_return: 0.25,
  max_drawdown: -0.08,
  sharpe_ratio: 1.5,
  trades: 42,
}

// ====================================================================
// usePositions
// ====================================================================
describe('usePositions', () => {
  it('returns loading state initially', async () => {
    server.use(
      http.get('/api/portfolio', () => HttpResponse.json(mockPortfolio)),
    )
    const { result } = renderHook(() => usePositions(), { wrapper })
    expect(result.current.isLoading).toBe(true)
    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })

  it('returns portfolio data on success', async () => {
    server.use(
      http.get('/api/portfolio', () => HttpResponse.json(mockPortfolio)),
    )
    const { result } = renderHook(() => usePositions(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.total_value).toBe(100000)
    expect(result.current.data?.cash).toBe(20000)
    expect(result.current.data?.positions).toHaveLength(2)
  })

  it('returns position details correctly', async () => {
    server.use(
      http.get('/api/portfolio', () => HttpResponse.json(mockPortfolio)),
    )
    const { result } = renderHook(() => usePositions(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const aapl = result.current.data?.positions.find(
      (p) => p.symbol === 'AAPL',
    )
    expect(aapl?.side).toBe('long')
    expect(aapl?.size).toBe(100)
    expect(aapl?.entry_price).toBe(150)
    expect(aapl?.pnl).toBe(5000)
  })

  it('returns error on server failure', async () => {
    server.use(
      http.get('/api/portfolio', () =>
        HttpResponse.json({ error: 'Internal Server Error' }, { status: 500 }),
      ),
    )
    const { result } = renderHook(() => usePositions(), { wrapper })
    await waitFor(() => expect(result.current.error).toBeDefined())
    expect(result.current.data).toBeUndefined()
  })

  it('handles empty positions array', async () => {
    server.use(
      http.get('/api/portfolio', () => HttpResponse.json(emptyPortfolio)),
    )
    const { result } = renderHook(() => usePositions(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.positions).toHaveLength(0)
    expect(result.current.data?.market_value).toBe(0)
  })

  it('calls the correct API endpoint', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/portfolio', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(mockPortfolio)
      }),
    )
    const { result } = renderHook(() => usePositions(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(requestedUrl).toContain('/api/portfolio')
  })
})

// ====================================================================
// useOrders
// ====================================================================
describe('useOrders', () => {
  it('returns loading state initially', async () => {
    server.use(
      http.get('/api/trading/orders', () => HttpResponse.json(mockOrders)),
    )
    const { result } = renderHook(() => useOrders(), { wrapper })
    expect(result.current.isLoading).toBe(true)
    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })

  it('returns orders on success (no params)', async () => {
    server.use(
      http.get('/api/trading/orders', () => HttpResponse.json(mockOrders)),
    )
    const { result } = renderHook(() => useOrders(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as Order[]
    expect(data).toHaveLength(2)
    expect(data[0].symbol).toBe('AAPL')
    expect(data[0].side).toBe('buy')
  })

  it('returns orders filtered by status', async () => {
    server.use(
      http.get('/api/trading/orders', ({ request }) => {
        const url = new URL(request.url)
        expect(url.searchParams.get('status')).toBe('filled')
        return HttpResponse.json([mockOrders[1]])
      }),
    )
    const { result } = renderHook(() => useOrders({ status: 'filled' }), {
      wrapper,
    })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as Order[]
    expect(data).toHaveLength(1)
    expect(data[0].status).toBe('filled')
  })

  it('returns error on server failure', async () => {
    server.use(
      http.get('/api/trading/orders', () =>
        HttpResponse.json({ error: 'Service Unavailable' }, { status: 503 }),
      ),
    )
    const { result } = renderHook(() => useOrders(), { wrapper })
    await waitFor(() => expect(result.current.error).toBeDefined())
    expect(result.current.data).toBeUndefined()
  })

  it('handles empty orders array', async () => {
    server.use(
      http.get('/api/trading/orders', () => HttpResponse.json(emptyOrders)),
    )
    const { result } = renderHook(() => useOrders(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as Order[]
    expect(data).toHaveLength(0)
  })

  it('calls correct URL without params', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/trading/orders', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(mockOrders)
      }),
    )
    const { result } = renderHook(() => useOrders(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(requestedUrl).toBe('http://localhost:3000/api/trading/orders')
  })
})

// ====================================================================
// useMarketData
// ====================================================================
describe('useMarketData', () => {
  it('returns loading state initially with symbol', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useMarketData('AAPL'), { wrapper })
    expect(result.current.isLoading).toBe(true)
    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })

  it('returns market data on success', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useMarketData('AAPL'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as typeof mockBars
    expect(data).toHaveLength(2)
    expect(data[0].symbol).toBe('AAPL')
    expect(data[0].price).toBe(200)
  })

  it('does not fetch when symbol is null', () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useMarketData(null), { wrapper })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toBeUndefined()
  })

  it('passes symbol as query parameter', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/market/bars', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(mockBars)
      }),
    )
    const { result } = renderHook(() => useMarketData('TSLA'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(requestedUrl).toContain('symbol=TSLA')
  })

  it('returns error on server failure', async () => {
    server.use(
      http.get('/api/market/bars', () =>
        HttpResponse.json({ error: 'Not Found' }, { status: 404 }),
      ),
    )
    const { result } = renderHook(() => useMarketData('INVALID'), {
      wrapper,
    })
    await waitFor(() => expect(result.current.error).toBeDefined())
    expect(result.current.data).toBeUndefined()
  })

  it('handles empty market data response', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(emptyBars)),
    )
    const { result } = renderHook(() => useMarketData('AAPL'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as typeof mockBars
    expect(data).toHaveLength(0)
  })

  it('returns bar data with OHLCV fields', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useMarketData('AAPL'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const bar = (result.current.data as typeof mockBars)[0]
    expect(bar.open).toBe(197)
    expect(bar.high).toBe(205)
    expect(bar.low).toBe(195)
    expect(bar.close ?? bar.price).toBe(200)
    expect(bar.volume).toBe(1000000)
  })
})

// ====================================================================
// useKlines
// ====================================================================
describe('useKlines', () => {
  it('returns loading state initially with symbol', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useKlines('AAPL'), { wrapper })
    expect(result.current.isLoading).toBe(true)
    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })

  it('returns kline data on success with default frequency', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/market/bars', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(mockBars)
      }),
    )
    const { result } = renderHook(() => useKlines('AAPL'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as typeof mockBars
    expect(data).toHaveLength(2)
    expect(requestedUrl).toContain('frequency=daily')
  })

  it('respects custom frequency parameter', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/market/bars', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(mockBars)
      }),
    )
    const { result } = renderHook(() => useKlines('AAPL', 'weekly'), {
      wrapper,
    })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(requestedUrl).toContain('frequency=weekly')
    expect(requestedUrl).toContain('symbol=AAPL')
  })

  it('does not fetch when symbol is null', () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useKlines(null), { wrapper })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toBeUndefined()
  })

  it('returns error on server failure', async () => {
    server.use(
      http.get('/api/market/bars', () =>
        HttpResponse.json({ error: 'Bad Request' }, { status: 400 }),
      ),
    )
    const { result } = renderHook(() => useKlines('INVALID'), { wrapper })
    await waitFor(() => expect(result.current.error).toBeDefined())
    expect(result.current.data).toBeUndefined()
  })

  it('handles empty kline data response', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(emptyBars)),
    )
    const { result } = renderHook(() => useKlines('AAPL'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as typeof mockBars
    expect(data).toHaveLength(0)
  })

  it('returns kline data with correct symbol', async () => {
    server.use(
      http.get('/api/market/bars', () => HttpResponse.json(mockBars)),
    )
    const { result } = renderHook(() => useKlines('MSFT'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data as typeof mockBars
    expect(data[0].symbol).toBe('AAPL')
  })
})

// ====================================================================
// useBacktest
// ====================================================================
describe('useBacktest', () => {
  it('does not fetch when id is null', () => {
    server.use(
      http.get('/api/backtest/bt-1', () => HttpResponse.json(mockBacktestResult)),
    )
    const { result } = renderHook(() => useBacktest(null), { wrapper })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toBeUndefined()
  })

  it('returns loading state initially with valid id', async () => {
    server.use(
      http.get('/api/backtest/bt-1', () => HttpResponse.json(mockBacktestResult)),
    )
    const { result } = renderHook(() => useBacktest('bt-1'), { wrapper })
    expect(result.current.isLoading).toBe(true)
    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })

  it('returns backtest data on success', async () => {
    server.use(
      http.get('/api/backtest/bt-1', () => HttpResponse.json(mockBacktestResult)),
    )
    const { result } = renderHook(() => useBacktest('bt-1'), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.id).toBe('bt-1')
    expect(result.current.data?.total_return).toBe(0.25)
    expect(result.current.data?.sharpe_ratio).toBe(1.5)
  })

  it('returns error on server failure', async () => {
    server.use(
      http.get('/api/backtest/bt-1', () =>
        HttpResponse.json({ error: 'Not Found' }, { status: 404 }),
      ),
    )
    const { result } = renderHook(() => useBacktest('bt-1'), { wrapper })
    await waitFor(() => expect(result.current.error).toBeDefined())
    expect(result.current.data).toBeUndefined()
  })
})
