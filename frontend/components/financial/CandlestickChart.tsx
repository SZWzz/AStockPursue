// frontend/components/financial/CandlestickChart.tsx
'use client'

import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { OLED } from '@/lib/constants'

export function CandlestickChart({ data }: { data: { time: string; open: number; high: number; low: number; close: number; volume: number }[] }) {
  if (!data.length) return <div className="flex items-center justify-center h-[300px] text-[12px] text-[var(--foreground-muted)]">No data</div>

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data}>
        <XAxis dataKey="time" tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} />
        <YAxis tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: OLED.surface3, border: '1px solid ' + OLED.borderDefault, borderRadius: 6, fontSize: 12 }} labelStyle={{ color: OLED.foregroundSecondary }} />
        <Bar dataKey="volume" fill={OLED.borderDefault} opacity={0.3} yAxisId={1} />
        <Line type="monotone" dataKey="close" stroke={OLED.primary} dot={false} strokeWidth={1.5} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
