// frontend/components/strategy-lab/BacktestPanel.tsx
'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface BacktestPanelProps {
  onRun: (config: { symbol: string; startDate: string; endDate: string }) => void
  running: boolean
  result: { totalReturn?: number; sharpeRatio?: number; maxDrawdown?: number } | null
  configTitle?: string
  symbolLabel?: string
  startLabel?: string
  endLabel?: string
  runLabel?: string
  runningLabel?: string
  returnLabel?: string
  sharpeLabel?: string
  maxDDLabel?: string
}

export function BacktestPanel({
  onRun,
  running,
  result,
  configTitle = 'Backtest Config',
  symbolLabel = 'Symbol',
  startLabel = 'Start',
  endLabel = 'End',
  runLabel = '▶ Run Backtest',
  runningLabel = 'Running...',
  returnLabel = 'Return',
  sharpeLabel = 'Sharpe',
  maxDDLabel = 'Max DD',
}: BacktestPanelProps) {
  const [symbol, setSymbol] = useState('000001.SZ')
  const [startDate, setStartDate] = useState('2026-01-01')
  const [endDate, setEndDate] = useState('2026-06-20')

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4 space-y-3">
      <h3 className="text-[14px] font-semibold text-[var(--foreground)]">{configTitle}</h3>
      <div>
        <label className="text-[12px] text-[var(--foreground-muted)]">{symbolLabel}</label>
        <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="h-10 mt-1" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[12px] text-[var(--foreground-muted)]">{startLabel}</label>
          <Input value={startDate} onChange={(e) => setStartDate(e.target.value)} className="h-10 mt-1" />
        </div>
        <div>
          <label className="text-[12px] text-[var(--foreground-muted)]">{endLabel}</label>
          <Input value={endDate} onChange={(e) => setEndDate(e.target.value)} className="h-10 mt-1" />
        </div>
      </div>
      <Button
        onClick={() => onRun({ symbol, startDate, endDate })}
        disabled={running}
        className="w-full h-10"
      >
        {running ? runningLabel : runLabel}
      </Button>
      {result && (
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[var(--border-subtle)]">
          <div>
            <div className="text-[11px] text-[var(--foreground-muted)]">{returnLabel}</div>
            <div className={`text-[18px] font-mono font-semibold ${(result.totalReturn || 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'}`}>
              {((result.totalReturn || 0) * 100).toFixed(2)}%
            </div>
          </div>
          <div>
            <div className="text-[11px] text-[var(--foreground-muted)]">{sharpeLabel}</div>
            <div className="text-[18px] font-mono font-semibold text-[var(--foreground)]">
              {(result.sharpeRatio || 0).toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-[var(--foreground-muted)]">{maxDDLabel}</div>
            <div className="text-[18px] font-mono font-semibold text-[var(--down)]">
              {((result.maxDrawdown || 0) * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
