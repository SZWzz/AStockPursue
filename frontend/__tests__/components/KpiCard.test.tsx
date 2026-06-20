import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiCard } from '@/components/financial/KpiCard'

describe('KpiCard', () => {
  it('renders label and value', () => {
    render(<KpiCard label="Total Return" value="+12.5%" />)
    expect(screen.getByText('Total Return')).toBeInTheDocument()
    expect(screen.getByText('+12.5%')).toBeInTheDocument()
  })

  it('renders subtitle when provided', () => {
    render(<KpiCard label="Sharpe" value="1.85" sub="Since inception" />)
    expect(screen.getByText('Since inception')).toBeInTheDocument()
  })

  it('does not render subtitle when omitted', () => {
    const { container } = render(<KpiCard label="Max DD" value="-8.2%" />)
    // The sub div should not exist
    const subDivs = container.querySelectorAll('.text-\\[11px\\].text-\\[var\\(--foreground-secondary\\)\\]')
    expect(subDivs.length).toBe(0)
  })

  it('applies up trend color', () => {
    const { container } = render(<KpiCard label="Return" value="+5%" trend="up" />)
    const valueEl = screen.getByText('+5%')
    expect(valueEl.className).toContain('text-[var(--up)]')
  })

  it('applies down trend color', () => {
    const { container } = render(<KpiCard label="Return" value="-3%" trend="down" />)
    const valueEl = screen.getByText('-3%')
    expect(valueEl.className).toContain('text-[var(--down)]')
  })

  it('applies neutral color when no trend specified', () => {
    const { container } = render(<KpiCard label="Trades" value="42" />)
    const valueEl = screen.getByText('42')
    expect(valueEl.className).toContain('text-[var(--foreground)]')
  })
})
