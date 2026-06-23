import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StrategyCard } from '@/components/financial/StrategyCard'

const mockTemplate = {
  key: 'ma_crossover',
  name: '均线交叉策略',
  name_en: 'MA Crossover',
  description: '经典双均线交叉策略。快线上穿慢线做多，下穿做空。',
  category: 'trend',
  difficulty: 'beginner',
  markets: ['Crypto', 'USStock', 'Forex'],
  default_params: {
    fast_period: 10,
    slow_period: 30,
    timeframe: '1H',
  },
  tags: ['trend', 'moving-average', 'beginner'],
}

const mockStats = {
  sharpe: 1.85,
  max_drawdown: 0.15,
  annual_return: 0.22,
  win_rate: 0.55,
  installs: 1234,
  rating: 4.5,
}

describe('StrategyCard', () => {
  // ── Basic rendering ─────────────────────────────────────────────
  it('renders template name, name_en, and description', () => {
    render(<StrategyCard template={mockTemplate} />)
    expect(screen.getByText('均线交叉策略')).toBeInTheDocument()
    expect(screen.getByText('MA Crossover')).toBeInTheDocument()
    expect(screen.getByText('经典双均线交叉策略。快线上穿慢线做多，下穿做空。')).toBeInTheDocument()
  })

  it('renders category badge with correct color for trend', () => {
    render(<StrategyCard template={mockTemplate} />)
    const badge = screen.getByText('趋势跟踪')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-blue-100')
    expect(badge.className).toContain('text-blue-700')
  })

  it('renders category badge with correct color for mean_reversion', () => {
    const template = { ...mockTemplate, category: 'mean_reversion' }
    render(<StrategyCard template={template} />)
    const badge = screen.getByText('均值回归')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-green-100')
    expect(badge.className).toContain('text-green-700')
  })

  it('renders category badge with correct color for momentum', () => {
    const template = { ...mockTemplate, category: 'momentum' }
    render(<StrategyCard template={template} />)
    const badge = screen.getByText('动量')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-orange-100')
  })

  // ── Stats rendering ─────────────────────────────────────────────
  it('renders stats when provided', () => {
    render(<StrategyCard template={mockTemplate} stats={mockStats} />)
    expect(screen.getByText('1.85')).toBeInTheDocument()
    expect(screen.getByText('22.0%')).toBeInTheDocument()
    expect(screen.getByText('15.0%')).toBeInTheDocument()
  })

  it('renders sharpe stat label', () => {
    render(<StrategyCard template={mockTemplate} stats={mockStats} />)
    expect(screen.getByText('夏普')).toBeInTheDocument()
    expect(screen.getByText('年化')).toBeInTheDocument()
    expect(screen.getByText('回撤')).toBeInTheDocument()
  })

  it('falls back to — when no stats provided', () => {
    render(<StrategyCard template={mockTemplate} />)
    expect(screen.queryByText('夏普')).not.toBeInTheDocument()
    expect(screen.queryByText('年化')).not.toBeInTheDocument()
  })

  it('falls back to — for individual missing stat values', () => {
    const partialStats = { annual_return: 0.22 }
    render(<StrategyCard template={mockTemplate} stats={partialStats} />)
    expect(screen.getByText('22.0%')).toBeInTheDocument()
    expect(screen.getAllByText('—')).toHaveLength(2)
  })

  it('displays zero sharpe correctly', () => {
    const zeroStats = { sharpe: 0, max_drawdown: 0, annual_return: 0 }
    render(<StrategyCard template={mockTemplate} stats={zeroStats} />)
    expect(screen.getByText('0.00')).toBeInTheDocument()
    expect(screen.getAllByText('0.0%')).toHaveLength(2)
  })

  // ── Rating and installs ─────────────────────────────────────────
  it('renders rating when provided', () => {
    render(<StrategyCard template={mockTemplate} stats={{ rating: 4.5 }} />)
    expect(screen.getByText('4.5')).toBeInTheDocument()
  })

  it('renders installs when provided', () => {
    render(<StrategyCard template={mockTemplate} stats={{ installs: 1234 }} />)
    expect(screen.getByText('1234')).toBeInTheDocument()
  })

  it('renders both rating and installs', () => {
    render(<StrategyCard template={mockTemplate} stats={{ rating: 4.5, installs: 1234 }} />)
    expect(screen.getByText('4.5')).toBeInTheDocument()
    expect(screen.getByText('1234')).toBeInTheDocument()
  })

  // ── Tags ────────────────────────────────────────────────────────
  it('renders tags from template', () => {
    render(<StrategyCard template={mockTemplate} />)
    expect(screen.getByText('trend')).toBeInTheDocument()
    expect(screen.getByText('moving-average')).toBeInTheDocument()
    expect(screen.getByText('beginner')).toBeInTheDocument()
  })

  it('renders at most 3 tags', () => {
    const manyTags = {
      ...mockTemplate,
      tags: ['a', 'b', 'c', 'd', 'e'],
    }
    render(<StrategyCard template={manyTags} />)
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
    expect(screen.getByText('c')).toBeInTheDocument()
    expect(screen.queryByText('d')).not.toBeInTheDocument()
    expect(screen.queryByText('e')).not.toBeInTheDocument()
  })

  // ── Install button ──────────────────────────────────────────────
  it('renders install button when onInstall is provided', () => {
    render(<StrategyCard template={mockTemplate} onInstall={() => {}} />)
    expect(screen.getByText('安装')).toBeInTheDocument()
  })

  it('does not render install button when onInstall is not provided', () => {
    render(<StrategyCard template={mockTemplate} />)
    expect(screen.queryByText('安装')).not.toBeInTheDocument()
  })

  it('calls onInstall callback on install button click', () => {
    const onInstall = vi.fn()
    render(<StrategyCard template={mockTemplate} onInstall={onInstall} />)
    fireEvent.click(screen.getByText('安装'))
    expect(onInstall).toHaveBeenCalledTimes(1)
  })

  // ── Card click ──────────────────────────────────────────────────
  it('calls onClick callback when card is clicked', () => {
    const onClick = vi.fn()
    const { container } = render(<StrategyCard template={mockTemplate} onClick={onClick} />)
    const card = container.firstElementChild!
    fireEvent.click(card)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not trigger onClick when install button is clicked', () => {
    const onClick = vi.fn()
    const onInstall = vi.fn()
    render(<StrategyCard template={mockTemplate} onClick={onClick} onInstall={onInstall} />)
    fireEvent.click(screen.getByText('安装'))
    expect(onInstall).toHaveBeenCalledTimes(1)
    expect(onClick).not.toHaveBeenCalled()
  })

  // ── Edge cases ──────────────────────────────────────────────────
  it('handles unknown category with fallback color', () => {
    const template = { ...mockTemplate, category: 'unknown_cat' }
    render(<StrategyCard template={template} />)
    const badge = screen.getByText('unknown_cat')
    expect(badge.className).toContain('bg-gray-100')
    expect(badge.className).toContain('text-gray-700')
  })

  it('handles template without tags', () => {
    const template = { ...mockTemplate, tags: [] as string[] }
    render(<StrategyCard template={template} />)
    expect(screen.getByText('均线交叉策略')).toBeInTheDocument()
  })

  it('handles negative stats values', () => {
    const negativeStats = {
      sharpe: -0.5,
      max_drawdown: -0.3,
      annual_return: -0.1,
    }
    render(<StrategyCard template={mockTemplate} stats={negativeStats} />)
    expect(screen.getByText('-0.50')).toBeInTheDocument()
    expect(screen.getByText('-10.0%')).toBeInTheDocument()
    expect(screen.getByText('-30.0%')).toBeInTheDocument()
  })

  it('renders install button without onClick handler on the card', () => {
    const onInstall = vi.fn()
    render(<StrategyCard template={mockTemplate} onInstall={onInstall} />)
    const button = screen.getByText('安装')
    fireEvent.click(button)
    expect(onInstall).toHaveBeenCalledTimes(1)
  })
})
