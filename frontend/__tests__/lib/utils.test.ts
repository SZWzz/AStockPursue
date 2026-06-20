import { describe, it, expect } from 'vitest'
import { cn, formatPrice, formatPercent, formatPnL, formatVolume, formatDateTime, colorForChange } from '@/lib/utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'extra')).toBe('base extra')
  })

  it('merges tailwind conflicts via twMerge', () => {
    expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4')
  })

  it('handles empty input', () => {
    expect(cn()).toBe('')
  })
})

describe('formatPrice', () => {
  it('formats price with default 2 decimals', () => {
    expect(formatPrice(123.456)).toBe('123.46')
  })

  it('formats integer price', () => {
    expect(formatPrice(100)).toBe('100.00')
  })

  it('formats with custom decimals', () => {
    expect(formatPrice(123.456, 3)).toBe('123.456')
  })
})

describe('formatPercent', () => {
  it('formats positive percent with + sign', () => {
    expect(formatPercent(0.0523)).toBe('+5.23%')
  })

  it('formats negative percent', () => {
    expect(formatPercent(-0.031)).toBe('-3.10%')
  })

  it('formats zero', () => {
    expect(formatPercent(0)).toBe('0.00%')
  })

  it('formats with custom decimals', () => {
    expect(formatPercent(0.12345, 1)).toBe('+12.3%')
  })
})

describe('formatPnL', () => {
  it('formats positive PnL with + sign', () => {
    expect(formatPnL(1500.5)).toBe('+1500.50')
  })

  it('formats negative PnL', () => {
    expect(formatPnL(-230.75)).toBe('-230.75')
  })

  it('formats zero PnL with + sign', () => {
    expect(formatPnL(0)).toBe('+0.00')
  })
})

describe('formatVolume', () => {
  it('formats volume in yi (100 million)', () => {
    expect(formatVolume(150000000)).toBe('1.50亿')
  })

  it('formats volume in wan (10 thousand)', () => {
    expect(formatVolume(50000)).toBe('5.00万')
  })

  it('formats small volume with locale', () => {
    expect(formatVolume(5000)).toBe('5,000')
  })
})

describe('formatDateTime', () => {
  it('returns a string for a timestamp number', () => {
    const result = formatDateTime(1718841600)
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('returns a string for an ISO string', () => {
    const result = formatDateTime('2024-06-20T00:00:00Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('colorForChange', () => {
  it('returns up color class for positive', () => {
    expect(colorForChange(0.5)).toBe('text-[var(--up)]')
  })

  it('returns down color class for negative', () => {
    expect(colorForChange(-0.3)).toBe('text-[var(--down)]')
  })

  it('returns secondary color class for zero', () => {
    expect(colorForChange(0)).toBe('text-[var(--foreground-secondary)]')
  })
})
