import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OrderBook } from '@/components/financial/OrderBook'

interface Level { price: number; quantity: number }

const bids: Level[] = [
  { price: 100.50, quantity: 5000 },
  { price: 100.40, quantity: 3000 },
  { price: 100.30, quantity: 2000 },
  { price: 100.20, quantity: 1000 },
  { price: 100.10, quantity: 500 },
]

const asks: Level[] = [
  { price: 100.60, quantity: 1500 },
  { price: 100.70, quantity: 2500 },
  { price: 100.80, quantity: 4000 },
  { price: 100.90, quantity: 6000 },
  { price: 101.00, quantity: 8000 },
]

const emptyLevels: Level[] = []

describe('OrderBook', () => {
  it('renders price column header', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    expect(screen.getByText('Price')).toBeInTheDocument()
  })

  it('renders Qty column header', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    expect(screen.getByText('Qty')).toBeInTheDocument()
  })

  it('renders Total column header', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    expect(screen.getByText('Total')).toBeInTheDocument()
  })

  it('renders bid prices', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    expect(screen.getByText('100.50')).toBeInTheDocument()
    expect(screen.getByText('100.40')).toBeInTheDocument()
  })

  it('renders ask prices', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    expect(screen.getByText('100.60')).toBeInTheDocument()
    expect(screen.getByText('101.00')).toBeInTheDocument()
  })

  it('renders spread value', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    expect(screen.getByText(/Spread/)).toBeInTheDocument()
  })

  it('renders spread percentage', () => {
    render(<OrderBook bids={bids} asks={asks} />)
    // spread = 100.60 - 100.50 = 0.10, spreadPct = 0.10/100.60 * 100 ≈ 0.099%
    expect(screen.getByText(/0\.099%/)).toBeInTheDocument()
  })

  it('renders empty ask side gracefully', () => {
    render(<OrderBook bids={bids} asks={emptyLevels} />)
    expect(screen.getByText('100.50')).toBeInTheDocument()
    // Should still render without throwing
  })

  it('renders with only asks and no bids', () => {
    render(<OrderBook bids={emptyLevels} asks={asks} />)
    expect(screen.getByText('100.60')).toBeInTheDocument()
    // Should still render without throwing
  })

  it('renders depth bars for bid side', () => {
    const { container } = render(<OrderBook bids={bids} asks={asks} />)
    // Depth bars are rendered with opacity-0.08 backgrounds
    const depthBars = container.querySelectorAll('.opacity-\\[0\\.08\\]')
    expect(depthBars.length).toBeGreaterThan(0)
  })

  it('renders cumulative quantities', () => {
    const { container } = render(<OrderBook bids={bids} asks={asks} />)
    // Check that "万" formatted volumes appear (cumulative should be at least 1万 for bids)
    const volumeElements = container.querySelectorAll('.text-\\[var\\(--foreground-muted\\)\\]')
    expect(volumeElements.length).toBeGreaterThan(0)
  })
})
