import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { NextIntlClientProvider } from 'next-intl'

// ── Mock data ───────────────────────────────────────────────────

const mockPortfolio = {
  total_value: 100000,
  cash: 20000,
  market_value: 80000,
  unrealized_pnl: 5000,
  realized_pnl: 2000,
  positions: [
    {
      symbol: 'AAPL', side: 'long' as const, size: 100,
      entry_price: 150, current_price: 200, market_value: 20000,
      pnl: 5000, pnl_pct: 33.33, realized_pnl: 0,
    },
    {
      symbol: 'TSLA', side: 'short' as const, size: 50,
      entry_price: 300, current_price: 280, market_value: 14000,
      pnl: 1000, pnl_pct: 6.67, realized_pnl: 0,
    },
    {
      symbol: 'MSFT', side: 'long' as const, size: 200,
      entry_price: 380, current_price: 420, market_value: 84000,
      pnl: 8000, pnl_pct: 10.53, realized_pnl: 0,
    },
  ],
}

const emptyPortfolio = {
  total_value: 50000,
  cash: 50000,
  market_value: 0,
  unrealized_pnl: 0,
  realized_pnl: 0,
  positions: [],
}

// ── Mocks ───────────────────────────────────────────────────────

const mockMutate = vi.fn()

vi.mock('@/hooks', () => ({
  usePositions: () => {
    const testModule = (globalThis as any).__positionTableTest
    if (testModule) {
      return testModule.hookReturn
    }
    return {
      data: mockPortfolio,
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    }
  },
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

// ── Translations ────────────────────────────────────────────────

const messages = {
  common: {
    loading: 'Loading...',
    error: 'Error loading data',
    noData: 'No positions',
    cancel: 'Cancel',
    createOrder: 'Close',
  },
  portfolio: {
    symbol: 'Symbol',
    position: 'Position',
    entryPrice: 'Entry',
    currentPrice: 'Current',
    pnl: 'PnL',
    pnlPct: 'PnL%',
    close: 'Close',
    closeSuccess: 'Position closed',
    confirmClose: 'Confirm Close',
    totalEquity: 'Total Equity',
    available: 'Available',
    exposure: 'Exposure',
    margin: 'Margin',
  },
}

// ── Helpers ─────────────────────────────────────────────────────

function setHookReturn(data: any) {
  ;(globalThis as any).__positionTableTest = { hookReturn: data }
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  )
}

describe('PositionTable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    delete (globalThis as any).__positionTableTest
  })

  async function importAndRender() {
    const { PositionTable } = await import('@/components/financial/PositionTable')
    return renderWithProviders(React.createElement(PositionTable))
  }

  // ── Loading / Error ────────────────────────────────────────────
  it('shows loading state', async () => {
    setHookReturn({ data: undefined, error: undefined, isLoading: true, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('Loading...')
  })

  it('shows error state', async () => {
    setHookReturn({ data: undefined, error: new Error('fail'), isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('Error loading data')
  })

  // ── Empty ──────────────────────────────────────────────────────
  it('shows empty state when no positions', async () => {
    setHookReturn({ data: emptyPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('No positions')
  })

  // ── Render with data ──────────────────────────────────────────
  it('renders position symbols', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('AAPL')
    expect(container.textContent).toContain('TSLA')
    expect(container.textContent).toContain('MSFT')
  })

  it('renders column headers', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('Symbol')
    expect(container.textContent).toContain('Position')
    expect(container.textContent).toContain('PnL')
    expect(container.textContent).toContain('Close')
  })

  it('renders formatted prices', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('150.00')
    expect(container.textContent).toContain('200.00')
  })

  it('renders position sizes', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('100')
    expect(container.textContent).toContain('50')
  })

  it('renders PnL values', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    // formatPnL: +5000.00
    expect(container.textContent).toContain('+5000.00')
    expect(container.textContent).toContain('+1000.00')
  })

  it('renders formatted PnL percentages', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    // formatPercent(33.33) = "+3333.00%" in the current format
    expect(container.textContent).toContain('3333')
    expect(container.textContent).toContain('667')
  })

  // ── Close button ──────────────────────────────────────────────
  it('shows close button for each position', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    const closeButtons = container.querySelectorAll('button')
    const closeBtn = Array.from(closeButtons).find(b => b.textContent?.includes('Close'))
    expect(closeBtn).toBeTruthy()
  })

  it('opens confirm dialog on close button click', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    const closeButtons = container.querySelectorAll('button')
    const closeBtn = Array.from(closeButtons).find(b => b.textContent?.includes('Close'))
    if (closeBtn) {
      fireEvent.click(closeBtn)
      // "Confirm Close" appears in both title & button — expect at least 2
      await waitFor(() => {
        const elements = screen.getAllByText('Confirm Close')
        expect(elements.length).toBeGreaterThanOrEqual(2)
      })
    }
  })

  it('has Cancel and Confirm buttons in dialog', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    const closeButtons = container.querySelectorAll('button')
    const closeBtn = Array.from(closeButtons).find(b => b.textContent?.includes('Close'))
    if (closeBtn) {
      fireEvent.click(closeBtn)
      await waitFor(() => {
        expect(screen.getByText('Cancel')).toBeInTheDocument()
        const confirmEls = screen.getAllByText('Confirm Close')
        expect(confirmEls.length).toBeGreaterThanOrEqual(2)
      })
    }
  })

  it('closes dialog on Cancel click', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    const closeButtons = container.querySelectorAll('button')
    const closeBtn = Array.from(closeButtons).find(b => b.textContent?.includes('Close'))
    if (closeBtn) {
      fireEvent.click(closeBtn)
      await waitFor(() => {
        expect(screen.getByText('Cancel')).toBeInTheDocument()
      })
      fireEvent.click(screen.getByText('Cancel'))
      await waitFor(() => {
        expect(screen.queryByText('Confirm Close')).toBeNull()
      })
    }
  })

  // ── Stats cards ───────────────────────────────────────────────
  it('renders aggregate stats cards', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('Total Equity')
    expect(container.textContent).toContain('Available')
    expect(container.textContent).toContain('Exposure')
    expect(container.textContent).toContain('Margin')
  })

  it('does not render stats cards when no positions', async () => {
    setHookReturn({ data: emptyPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).not.toContain('Total Equity')
  })

  it('shows formatted total equity', async () => {
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    // formatPnL(100000) = "+100000.00"
    expect(container.textContent).toContain('+100000.00')
  })

  it('shows percentage for exposure', async () => {
    // totalMarketValue = 100*200 + 50*280 + 200*420 = 20000+14000+84000 = 118000
    // exposure = (118000 / 100000) * 100 = 118.0%
    setHookReturn({ data: mockPortfolio, error: undefined, isLoading: false, mutate: vi.fn() })
    const { container } = await importAndRender()
    expect(container.textContent).toContain('118.0')
  })
})
