// frontend/components/strategy-lab/ChartPanel.tsx
'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface ChartPanelProps {
  equityData: { time: string; equity: number }[]
  title?: string
  emptyHint?: string
}

export function ChartPanel({ equityData, title = 'Equity Curve', emptyHint = 'Run a backtest to see results' }: ChartPanelProps) {
  if (!equityData.length) {
    return (
      <div className="bg-white border border-[var(--border)] rounded-[6px] p-6 flex items-center justify-center h-[300px]">
        <span className="text-[14px] text-[var(--foreground-muted)]">{emptyHint}</span>
      </div>
    )
  }

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4">
      <h3 className="text-[14px] font-semibold text-[var(--foreground)] mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={equityData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--foreground-muted)' }} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--foreground-muted)' }} />
          <Tooltip
            contentStyle={{
              background: '#fff',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              fontSize: '13px',
            }}
          />
          <Line type="monotone" dataKey="equity" stroke="var(--primary)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
