// frontend/app/strategy-lab/page.tsx
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CodeEditor } from '@/components/strategy-lab/CodeEditor'
import { ChartPanel } from '@/components/strategy-lab/ChartPanel'
import { BacktestPanel } from '@/components/strategy-lab/BacktestPanel'

const DEFAULT_CODE = `# Strategy: Momentum Breakout
# Symbol: {symbol}  |  Period: {start} → {end}

def generate(df, params):
    fast = params.get('fast', 5)
    slow = params.get('slow', 20)
    df['ma_fast'] = df['close'].rolling(fast).mean()
    df['ma_slow'] = df['close'].rolling(slow).mean()
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
    return df
`

export default function StrategyLabPage() {
  const t = useTranslations()
  const [code, setCode] = useState(DEFAULT_CODE)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, number> | null>(null)
  const [equityData, setEquityData] = useState<{ time: string; equity: number }[]>([])

  const handleRun = async (config: { symbol: string; startDate: string; endDate: string }) => {
    setRunning(true)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: `${config.symbol}_${config.startDate}_${config.endDate}`,
          symbol: config.symbol,
          start_date: config.startDate,
          end_date: config.endDate,
          frequency: 'daily',
          initial_capital: 100000,
          code,
        }),
      })
      if (!res.ok) throw new Error('Backtest failed')
      const data = await res.json()
      setResult({
        totalReturn: data.total_return || 0,
        sharpeRatio: data.sharpe_ratio || 0,
        maxDrawdown: data.max_drawdown || 0,
      })
      if (data.equity_curve) {
        setEquityData(data.equity_curve.map((e: { time: string; equity: number }) => ({
          time: e.time?.slice(0, 10) || '',
          equity: e.equity,
        })))
      }
    } catch {
      setResult(null)
    } finally {
      setRunning(false)
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          Strategy Lab
        </h1>
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8 space-y-4">
            <CodeEditor code={code} onChange={(v) => setCode(v ?? '')} height="400px" />
            <ChartPanel equityData={equityData} />
          </div>
          <div className="col-span-4">
            <BacktestPanel onRun={handleRun} running={running} result={result} />
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
