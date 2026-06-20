// frontend/components/financial/CandlestickChart.tsx
'use client'

import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const upColor = '#05B169'
const downColor = '#CF202F'
const gridColor = '#EEF0F3'

export function CandlestickChart({ data }: { data: { time: string; open: number; high: number; low: number; close: number; volume: number }[] }) {
  if (!data.length) return <div className="flex items-center justify-center h-[300px] text-[12px] text-[var(--foreground-muted)]">No data</div>

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px]">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <XAxis dataKey="time" tick={{ fill: '#5E6673', fontSize: 10 }} axisLine={{ stroke: gridColor }} tickLine={false} />
          <YAxis tick={{ fill: '#5E6673', fontSize: 10 }} axisLine={{ stroke: gridColor }} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ background: '#fff', border: '1px solid ' + gridColor, borderRadius: 6, fontSize: 14 }} labelStyle={{ color: '#5E6673' }} />
          <Bar dataKey="volume" fill={gridColor} opacity={0.3} yAxisId={1} />
          <Line type="monotone" dataKey="close" stroke={upColor} dot={false} strokeWidth={1.5} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
