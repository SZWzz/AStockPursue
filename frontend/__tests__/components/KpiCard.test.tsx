import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiCard } from '@/components/financial/KpiCard'

describe('KpiCard', () => {
  // ── Basic rendering ─────────────────────────────────────────────
  it('renders label and value', () => {
    render(<KpiCard label="Total Return" value="+12.5%" />)
    expect(screen.getByText('Total Return')).toBeInTheDocument()
    expect(screen.getByText('+12.5%')).toBeInTheDocument()
  })

  it('renders change when provided', () => {
    render(<KpiCard label="Sharpe" value="1.85" change="Since inception" />)
    expect(screen.getByText('Since inception')).toBeInTheDocument()
  })

  it('does not render change when omitted', () => {
    const { container } = render(<KpiCard label="Max DD" value="-8.2%" />)
    const changeEl = container.querySelector('.flex.items-center.gap-1')
    expect(changeEl).toBeNull()
  })

  // ── Direction indicators ────────────────────────────────────────
  it('shows up arrow for up direction', () => {
    render(<KpiCard label="Return" value="+5%" change="+5.0%" direction="up" />)
    expect(screen.getByText('▲')).toBeInTheDocument()
    expect(screen.getByText('+5.0%')).toBeInTheDocument()
  })

  it('shows down arrow for down direction', () => {
    render(<KpiCard label="Return" value="-3%" change="-3.0%" direction="down" />)
    expect(screen.getByText('▼')).toBeInTheDocument()
    expect(screen.getByText('-3.0%')).toBeInTheDocument()
  })

  it('shows no arrow for neutral direction', () => {
    const { container } = render(<KpiCard label="Trades" value="42" change="+0" direction="neutral" />)
    const arrowEl = container.querySelector('.flex.items-center.gap-1 span:first-child')
    expect(arrowEl?.textContent).toBe('')
  })

  // ── Value formatting — positive / negative / zero ──────────────
  it('displays positive value correctly', () => {
    render(<KpiCard label="PnL" value="+1,234.56" change="+234.56" direction="up" />)
    expect(screen.getByText('+1,234.56')).toBeInTheDocument()
  })

  it('displays negative value correctly', () => {
    render(<KpiCard label="PnL" value="-567.89" change="-5.68%" direction="down" />)
    expect(screen.getByText('-567.89')).toBeInTheDocument()
    expect(screen.getByText('-5.68%')).toBeInTheDocument()
  })

  it('displays zero value correctly', () => {
    render(<KpiCard label="Change" value="0.00" change="+0.00" direction="neutral" />)
    expect(screen.getByText('0.00')).toBeInTheDocument()
    expect(screen.getByText('+0.00')).toBeInTheDocument()
  })

  // ── Large numbers ──────────────────────────────────────────────
  it('handles large positive values', () => {
    render(<KpiCard label="Market Cap" value="1,234,567,890" change="+12.5亿" direction="up" />)
    expect(screen.getByText('1,234,567,890')).toBeInTheDocument()
    expect(screen.getByText('+12.5亿')).toBeInTheDocument()
  })

  it('handles large negative values', () => {
    render(<KpiCard label="Drawdown" value="-98,765,432" change="-1.2亿" direction="down" />)
    expect(screen.getByText('-98,765,432')).toBeInTheDocument()
  })

  // ── Change text no direction ───────────────────────────────────
  it('renders change text without direction', () => {
    const { container } = render(<KpiCard label="Volume" value="5000" change="+12%" />)
    expect(screen.getByText('+12%')).toBeInTheDocument()
    const arrowEl = container.querySelector('.flex.items-center.gap-1 span:first-child')
    expect(arrowEl?.textContent).toBe('')
  })

  // ── Percent symbols ────────────────────────────────────────────
  it('renders percentage values', () => {
    render(<KpiCard label="Win Rate" value="65.5%" change="+2.3%" direction="up" />)
    expect(screen.getByText('65.5%')).toBeInTheDocument()
  })
})
