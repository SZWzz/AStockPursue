// frontend/components/financial/EquityChart.tsx
'use client'

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { OLED } from '@/lib/constants'

export function EquityChart({ data }: { data: { time: string | number; equity: number }[] }) {
  if (!data.length) return <div className="flex items-center justify-center h-[250px] text-[12px] text-[var(--foreground-muted)]">No data</div>
  const initial = data[0]?.equity || 0

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={OLED.up} stopOpacity={0.15} />
            <stop offset="100%" stopColor={OLED.up} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="time" tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} />
        <YAxis tick={{ fill: OLED.foregroundMuted, fontSize: 10 }} axisLine={{ stroke: OLED.borderSubtle }} tickLine={false} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: OLED.surface3, border: '1px solid ' + OLED.borderDefault, borderRadius: 6, fontSize: 12 }} />
        <ReferenceLine y={initial} stroke={OLED.borderDefault} strokeDasharray="4 3" />
        <Area type="monotone" dataKey="equity" stroke={OLED.up} strokeWidth={1.5} fill="url(#equityFill)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
