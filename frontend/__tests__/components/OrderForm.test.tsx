import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { OrderForm } from '@/components/financial/OrderForm'
import { NextIntlClientProvider } from 'next-intl'
import { useOrderFormStore } from '@/stores'

const messages = {
  trading: {
    submit: 'Submit Order',
    buy: 'Buy',
    sell: 'Sell',
    symbol: 'Symbol',
    orderType: 'Order Type',
    limit: 'Limit',
    market: 'Market',
    quantity: 'Quantity',
    price: 'Price',
  },
  common: { actions: 'Actions' },
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  )
}

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch as any

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('OrderForm', () => {
  beforeEach(() => {
    useOrderFormStore.getState().reset()
    vi.clearAllMocks()
  })

  // ── Existing tests (adapted) ───────────────────────────────────
  it('renders buy/sell toggle', () => {
    renderWithProviders(<OrderForm />)
    const buyElements = screen.getAllByText('Buy')
    expect(buyElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Sell')).toBeInTheDocument()
  })

  it('renders symbol input', () => {
    renderWithProviders(<OrderForm />)
    // Symbol input should be the first textbox
    const textboxes = screen.getAllByRole('textbox')
    expect(textboxes.length).toBeGreaterThanOrEqual(1)
    expect(textboxes[0]).toBeInTheDocument()
  })

  it('renders submit button', () => {
    renderWithProviders(<OrderForm />)
    expect(screen.getByRole('button', { name: /Buy/i })).toBeInTheDocument()
  })

  it('shows price field for limit orders', () => {
    renderWithProviders(<OrderForm />)
    expect(screen.getByText('Price')).toBeInTheDocument()
  })

  // ── Buy/Sell toggle ────────────────────────────────────────────
  it('switches to sell when Sell button clicked', () => {
    renderWithProviders(<OrderForm />)
    fireEvent.click(screen.getByText('Sell'))
    expect(screen.getByRole('button', { name: /Sell/i })).toBeInTheDocument()
  })

  it('submit button shows current symbol', () => {
    useOrderFormStore.setState({ symbol: 'AAPL' })
    renderWithProviders(<OrderForm />)
    expect(screen.getByRole('button', { name: /Buy AAPL/i })).toBeInTheDocument()
  })

  // ── Symbol input ───────────────────────────────────────────────
  it('uppercases symbol input', () => {
    renderWithProviders(<OrderForm />)
    const textboxes = screen.getAllByRole('textbox')
    const symbolInput = textboxes[0] as HTMLInputElement
    fireEvent.change(symbolInput, { target: { value: 'aapl' } })
    expect(symbolInput).toHaveValue('AAPL')
  })

  // ── Quantity input ─────────────────────────────────────────────
  it('quantity input updates store state', () => {
    renderWithProviders(<OrderForm />)
    // Quantity input has type="number" (role "spinbutton")
    const spinbuttons = screen.getAllByRole('spinbutton')
    const quantityInput = spinbuttons[0] as HTMLInputElement
    fireEvent.change(quantityInput, { target: { value: '100' } })
    expect(useOrderFormStore.getState().quantity).toBe('100')
  })

  // ── Order type — no price for market ───────────────────────────
  it('hides price field for market orders', () => {
    useOrderFormStore.setState({ orderType: 'market' })
    renderWithProviders(<OrderForm />)
    expect(screen.queryByText('Price')).toBeNull()
  })

  // ── Price input ────────────────────────────────────────────────
  it('price input updates store state for limit orders', () => {
    renderWithProviders(<OrderForm />)
    // Price input has type="number" (role "spinbutton"), index 1
    const spinbuttons = screen.getAllByRole('spinbutton')
    const priceInput = spinbuttons[1] as HTMLInputElement
    fireEvent.change(priceInput, { target: { value: '150.50' } })
    expect(useOrderFormStore.getState().price).toBe('150.50')
  })

  // ── Form submit ────────────────────────────────────────────────
  it('calls API on form submit', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })
    useOrderFormStore.setState({
      symbol: 'AAPL', side: 'buy', orderType: 'limit',
      price: '150.00', quantity: '100',
    })
    renderWithProviders(<OrderForm />)
    const submitButton = screen.getByRole('button', { name: /Buy AAPL/i })
    fireEvent.click(submitButton)
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/trading/orders',
        expect.objectContaining({ method: 'POST' })
      )
    })
  })

  it('sends correct order payload', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })
    useOrderFormStore.setState({
      symbol: 'MSFT', side: 'sell', orderType: 'limit',
      price: '420.00', quantity: '50',
    })
    renderWithProviders(<OrderForm />)
    fireEvent.click(screen.getByRole('button', { name: /Sell MSFT/i }))
    await waitFor(() => {
      const body = JSON.parse(mockFetch.mock.calls[0][1].body)
      expect(body.symbol).toBe('MSFT')
      expect(body.side).toBe('sell')
      expect(body.type).toBe('limit')
      expect(body.price).toBe(420)
      expect(body.quantity).toBe(50)
    })
  })

  it('sends market order payload without price', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })
    useOrderFormStore.setState({
      symbol: 'GOOGL', side: 'buy', orderType: 'market',
      quantity: '10',
    })
    renderWithProviders(<OrderForm />)
    fireEvent.click(screen.getByRole('button', { name: /Buy GOOGL/i }))
    await waitFor(() => {
      const body = JSON.parse(mockFetch.mock.calls[0][1].body)
      expect(body.type).toBe('market')
      expect(body.quantity).toBe(10)
    })
  })
})
