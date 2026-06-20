import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiCard } from '@/components/financial/KpiCard'

describe('KpiCard', () => {
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
})
