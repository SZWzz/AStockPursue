import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ScreenerGrid } from '@/components/financial/ScreenerGrid'
import type { ScreenerRow } from '@/components/financial/ScreenerGrid'
import { NextIntlClientProvider } from 'next-intl'

const messages = {
  common: { noData: 'No Data', actions: 'Actions' },
  trading: { symbol: 'Symbol', price: 'Price' },
  screener: { change: 'Change', volume: 'Volume', score: 'Score' },
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  )
}

const mockData: ScreenerRow[] = [
  { symbol: 'AAPL', price: 200.50, change_pct: 2.5, volume: 10000000, name: 'Apple', score: 85, rank: 1 },
  { symbol: 'TSLA', price: 280.00, change_pct: -1.2, volume: 5000000, name: 'Tesla', score: 45, rank: 2 },
  { symbol: 'MSFT', price: 420.00, change_pct: 0.8, volume: 8000000, name: 'Microsoft', score: 70, rank: 3 },
  { symbol: 'GOOGL', price: 175.30, change_pct: 3.1, volume: 12000000, name: 'Google', score: 90, rank: 4 },
  { symbol: 'AMZN', price: 185.00, change_pct: -0.5, volume: 6000000, name: 'Amazon', score: 30, rank: 5 },
]

const emptyData: ScreenerRow[] = []

describe('ScreenerGrid', () => {
  // ── Filter mode (default) ──────────────────────────────────────
  it('renders columns in filter mode', () => {
    renderWithProviders(<ScreenerGrid data={mockData} mode="filter" />)
    expect(screen.getByText('Symbol')).toBeInTheDocument()
    expect(screen.getByText('Price')).toBeInTheDocument()
    expect(screen.getByText('Change')).toBeInTheDocument()
    expect(screen.getByText('Volume')).toBeInTheDocument()
  })

  it('renders all rows in filter mode', () => {
    renderWithProviders(<ScreenerGrid data={mockData} mode="filter" />)
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
    expect(screen.getByText('GOOGL')).toBeInTheDocument()
    expect(screen.getByText('AMZN')).toBeInTheDocument()
  })

  it('renders formatted prices in filter mode', () => {
    renderWithProviders(<ScreenerGrid data={mockData} mode="filter" />)
    expect(screen.getByText('200.50')).toBeInTheDocument()
    expect(screen.getByText('280.00')).toBeInTheDocument()
  })

  // ── Rank mode ──────────────────────────────────────────────────
  it('renders rank column in rank mode', () => {
    renderWithProviders(<ScreenerGrid data={mockData} mode="rank" />)
    expect(screen.getByText('#')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('uses rank field when available in rank mode', () => {
    // rank column should show the explicit rank values
    renderWithProviders(<ScreenerGrid data={mockData} mode="rank" />)
    const rankCells = screen.getAllByText(/^1$|^2$|^3$|^4$|^5$/)
    expect(rankCells.length).toBeGreaterThanOrEqual(5)
  })

  it('falls back to index+1 when rank is undefined', () => {
    const dataWithoutRank: ScreenerRow[] = [
      { symbol: 'AAPL', price: 200, change_pct: 2.5, volume: 10000000 },
      { symbol: 'TSLA', price: 280, change_pct: -1.2, volume: 5000000 },
    ]
    renderWithProviders(<ScreenerGrid data={dataWithoutRank} mode="rank" />)
    // Should show 1 and 2 as fallback
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  // ── Score mode ─────────────────────────────────────────────────
  it('renders score column in score mode', () => {
    renderWithProviders(<ScreenerGrid data={mockData} mode="score" />)
    expect(screen.getByText('Score')).toBeInTheDocument()
  })

  it('renders score progress bars', () => {
    const { container } = renderWithProviders(<ScreenerGrid data={mockData} mode="score" />)
    // Score bars should be present
    const bars = container.querySelectorAll('.rounded-full.overflow-hidden')
    expect(bars.length).toBeGreaterThanOrEqual(5)
  })

  it('renders "--" for undefined score', () => {
    const dataNoScore: ScreenerRow[] = [
      { symbol: 'AAPL', price: 200, change_pct: 2.5, volume: 10000000 },
    ]
    renderWithProviders(<ScreenerGrid data={dataNoScore} mode="score" />)
    expect(screen.getByText('--')).toBeInTheDocument()
  })

  // ── Empty state ────────────────────────────────────────────────
  it('shows no data message when data is empty', () => {
    renderWithProviders(<ScreenerGrid data={emptyData} />)
    expect(screen.getByText('No Data')).toBeInTheDocument()
  })

  // ── Row click ──────────────────────────────────────────────────
  it('calls onRowClick when row is clicked', () => {
    const onRowClick = vi.fn()
    renderWithProviders(<ScreenerGrid data={mockData} mode="filter" onRowClick={onRowClick} />)
    fireEvent.click(screen.getByText('AAPL'))
    expect(onRowClick).toHaveBeenCalledWith('AAPL')
  })

  // ── Action column ──────────────────────────────────────────────
  it('renders action column when actionLabel and onAction provided', () => {
    const onAction = vi.fn()
    renderWithProviders(
      <ScreenerGrid data={mockData.slice(0, 1)} actionLabel="Buy" onAction={onAction} />
    )
    expect(screen.getByText('Actions')).toBeInTheDocument()
    expect(screen.getByText('Buy')).toBeInTheDocument()
  })

  it('calls onAction and stops propagation', () => {
    const onRowClick = vi.fn()
    const onAction = vi.fn()
    renderWithProviders(
      <ScreenerGrid
        data={mockData.slice(0, 1)}
        mode="filter"
        onRowClick={onRowClick}
        actionLabel="Buy"
        onAction={onAction}
      />
    )
    fireEvent.click(screen.getByText('Buy'))
    expect(onAction).toHaveBeenCalledWith('AAPL')
    expect(onRowClick).not.toHaveBeenCalled()
  })
})
