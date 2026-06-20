// frontend/components/financial/EquityChart.tsx
'use client'

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

const upColor = '#05B169'
const gridColor = '#EEF0F3'

export function EquityChart({ data }: { data: { time: string | number; equity: number }[] }) {
  if (!data.length) return <div className="flex items-center justify-center h-[250px] text-[12px] text-[var(--foreground-muted)]">No data</div>
  const initial = data[0]?.equity || 0

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px]">
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={upColor} stopOpacity={0.15} />
              <stop offset="100%" stopColor={upColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" tick={{ fill: '#5E6673', fontSize: 10 }} axisLine={{ stroke: gridColor }} tickLine={false} />
          <YAxis tick={{ fill: '#5E6673', fontSize: 10 }} axisLine={{ stroke: gridColor }} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ background: '#fff', border: '1px solid ' + gridColor, borderRadius: 6, fontSize: 14 }} />
          <ReferenceLine y={initial} stroke={gridColor} strokeDasharray="4 3" />
          <Area type="monotone" dataKey="equity" stroke={upColor} strokeWidth={1.5} fill="url(#equityFill)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
