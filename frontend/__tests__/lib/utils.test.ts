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

  it('handles undefined and null values', () => {
    expect(cn('base', undefined, null, 'extra')).toBe('base extra')
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

  it('formats zero', () => {
    expect(formatPrice(0)).toBe('0.00')
  })

  it('formats negative price', () => {
    expect(formatPrice(-100)).toBe('-100.00')
  })

  it('formats with 0 decimals', () => {
    expect(formatPrice(123.89, 0)).toBe('124')
  })

  it('formats very small positive number', () => {
    expect(formatPrice(0.001)).toBe('0.00')
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

  it('formats 100% (value 1)', () => {
    expect(formatPercent(1)).toBe('+100.00%')
  })

  it('formats very small positive value', () => {
    expect(formatPercent(0.00001)).toBe('+0.00%')
  })

  it('formats very small negative value', () => {
    expect(formatPercent(-0.00001)).toBe('-0.00%')
  })

  it('formats with 3 decimals', () => {
    expect(formatPercent(0.0123456, 3)).toBe('+1.235%')
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

  it('formats large number', () => {
    expect(formatPnL(1234567.89)).toBe('+1234567.89')
  })

  it('formats very small positive', () => {
    expect(formatPnL(0.001)).toBe('+0.00')
  })

  it('formats negative close to zero', () => {
    expect(formatPnL(-0.001)).toBe('-0.00')
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

  it('formats exactly 1 yi', () => {
    expect(formatVolume(100000000)).toBe('1.00亿')
  })

  it('formats exactly 1 wan', () => {
    expect(formatVolume(10000)).toBe('1.00万')
  })

  it('formats zero', () => {
    expect(formatVolume(0)).toBe('0')
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

  it('handles Unix epoch (timestamp 0)', () => {
    const result = formatDateTime(0)
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('handles future timestamp', () => {
    const result = formatDateTime(1893456000)
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('handles invalid date string gracefully', () => {
    const result = formatDateTime('invalid-date')
    expect(typeof result).toBe('string')
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

  it('returns secondary for NaN', () => {
    expect(colorForChange(NaN)).toBe('text-[var(--foreground-secondary)]')
  })

  it('returns up for Infinity', () => {
    expect(colorForChange(Infinity)).toBe('text-[var(--up)]')
  })
})
