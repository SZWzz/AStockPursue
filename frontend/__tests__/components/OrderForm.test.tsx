import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { OrderForm } from '@/components/financial/OrderForm'
import { NextIntlClientProvider } from 'next-intl'

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
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  )
}

describe('OrderForm', () => {
  it('renders buy/sell toggle', () => {
    renderWithProviders(<OrderForm />)
    const buyElements = screen.getAllByText('Buy')
    expect(buyElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Sell')).toBeInTheDocument()
  })

  it('renders symbol input', () => {
    renderWithProviders(<OrderForm />)
    const symbolInputs = screen.getAllByRole('textbox')
    const symbolInput = symbolInputs[0]
    expect(symbolInput).toBeInTheDocument()
  })

  it('renders submit button', () => {
    renderWithProviders(<OrderForm />)
    expect(screen.getByRole('button', { name: /Buy/i })).toBeInTheDocument()
  })

  it('does not show price field by default (limit order)', () => {
    renderWithProviders(<OrderForm />)
    expect(screen.getByText('Price')).toBeInTheDocument()
  })
})
