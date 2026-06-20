import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPrice(v: number, decimals = 2): string { return v.toFixed(decimals) }
export function formatPercent(v: number, decimals = 2): string { const sign = v > 0 ? '+' : ''; return `${sign}${(v * 100).toFixed(decimals)}%` }
export function formatVolume(v: number): string { if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`; if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`; return v.toLocaleString() }
export function formatPnL(v: number): string { const sign = v >= 0 ? '+' : ''; return `${sign}${v.toFixed(2)}` }
export function formatDateTime(ts: number | string): string { const d = new Date(typeof ts === 'string' ? ts : ts * 1000); return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
export function colorForChange(v: number): string { return v > 0 ? 'text-[var(--up)]' : v < 0 ? 'text-[var(--down)]' : 'text-[var(--foreground-secondary)]' }
