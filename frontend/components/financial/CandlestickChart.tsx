// frontend/components/financial/CandlestickChart.tsx
'use client'

import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Customized
} from 'recharts'

interface CandleData {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// A-share convention: up (close >= open) = red, down (close < open) = green
const upColor = '#CF202F'
const downColor = '#05B169'

// ── MA computation ─────────────────────────────────────────────────

const MA_PERIODS = [5, 10, 20, 60] as const
const MA_COLORS: Record<number, string> = { 5: '#FF9800', 10: '#2196F3', 20: '#9C27B0', 60: '#4CAF50' }
const MA_LABELS: Record<number, string> = { 5: 'MA5', 10: 'MA10', 20: 'MA20', 60: 'MA60' }

function computeMA(data: number[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += data[j]
    return sum / period
  })
}

// ── Custom Tooltip ──────────────────────────────────────────────────

function CandleTooltip({ active, payload }: any) {
  if (!active || !payload?.length || !payload[0]?.payload) return null
  const d = payload[0].payload as CandleData
  const change = d.close - d.open
  const changePct = d.open !== 0 ? ((change / d.open) * 100).toFixed(2) : '0.00'
  const isUp = change >= 0

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e0e0e0',
      borderRadius: 6,
      padding: '8px 12px',
      fontSize: 12,
      lineHeight: 1.7,
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4, color: '#333' }}>{d.time}</div>
      <div>O: <b>{d.open.toFixed(2)}</b></div>
      <div>H: <b>{d.high.toFixed(2)}</b></div>
      <div>L: <b>{d.low.toFixed(2)}</b></div>
      <div>C: <b>{d.close.toFixed(2)}</b></div>
      <div>V: {d.volume.toLocaleString()}</div>
      <div style={{ color: isUp ? upColor : downColor, fontWeight: 600 }}>
        {isUp ? '+' : ''}{change.toFixed(2)} ({changePct}%)
      </div>
    </div>
  )
}

// ── Custom Candle Renderer ──────────────────────────────────────────

function CandleRenderer(props: any) {
  const { formattedGraphicalItems, width, height, offset } = props

  if (!formattedGraphicalItems?.length) return null

  // The first graphical item's props contain the chart coordinate info
  const mainItem = formattedGraphicalItems[0]
  const data: CandleData[] = mainItem?.props?.data ?? []
  if (!data.length) return null

  // Extract Y scale from recharts internal state
  // We find the primary yAxis from the chart
  let yScale: any = null
  for (const axis of props.yAxisMap?.values?.() ?? []) {
    if (!axis?.scale) continue
    // Check if this is the primary price axis (not the volume axis)
    if (axis.yAxisId !== 'vol') {
      yScale = axis.scale
      break
    }
  }

  if (!yScale) return null

  const chartLeft = offset?.left ?? 0
  const chartTop = offset?.top ?? 0
  const chartWidth = width - (offset?.left ?? 0) - (offset?.right ?? 0)
  const chartHeight = height - (offset?.top ?? 0) - (offset?.bottom ?? 0)

  const n = data.length
  const barSpacing = n > 1 ? chartWidth / n : chartWidth
  const candleW = Math.max(1.5, Math.min(8, barSpacing * 0.55))
  const gap = (barSpacing - candleW) / 2

  return (
    <g>
      {data.map((d, i) => {
        const cx = chartLeft + i * barSpacing + barSpacing / 2

        const mapY = (v: number) => chartTop + yScale(v)
        const highY = mapY(d.high)
        const lowY = mapY(d.low)
        const openY = mapY(d.open)
        const closeY = mapY(d.close)

        const isUp = d.close >= d.open
        const color = isUp ? upColor : downColor
        const bodyTop = Math.min(openY, closeY)
        const bodyH = Math.max(1, Math.abs(closeY - openY))

        return (
          <g key={d.time}>
            {/* High-low wick */}
            <line
              x1={cx} y1={highY}
              x2={cx} y2={lowY}
              stroke={color} strokeWidth={1}
            />
            {/* Open-close body */}
            <rect
              x={cx - candleW / 2} y={bodyTop}
              width={candleW} height={bodyH}
              fill={isUp ? color : 'transparent'}
              stroke={color} strokeWidth={1}
            />
          </g>
        )
      })}
    </g>
  )
}

// ── Main Component ──────────────────────────────────────────────────

export function CandlestickChart({ data }: { data: CandleData[] }) {
  const [activeMAs, setActiveMAs] = useState<Set<number>>(new Set())

  const toggleMA = (period: number) => {
    setActiveMAs(prev => {
      const next = new Set(prev)
      if (next.has(period)) next.delete(period)
      else next.add(period)
      return next
    })
  }

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-[300px] text-[12px] text-[var(--foreground-muted)]">
        No data
      </div>
    )
  }

  const priceMin = Math.min(...data.map(d => d.low))
  const priceMax = Math.max(...data.map(d => d.high))
  const pricePadding = (priceMax - priceMin) * 0.05 || 1
  const yDomain: [number, number] = [priceMin - pricePadding, priceMax + pricePadding]

  const volMax = Math.max(...data.map(d => d.volume), 1)

  // Pre-compute all MA series
  const closePrices = useMemo(() => data.map(d => d.close), [data])
  const maSeries = useMemo(() => {
    const series: Record<number, (number | null)[]> = {}
    for (const p of MA_PERIODS) {
      series[p] = computeMA(closePrices, p)
    }
    return series
  }, [closePrices])

  // Build enriched data for Line components
  const enrichedData = useMemo(() => {
    return data.map((d, i) => {
      const entry: any = { ...d }
      for (const p of MA_PERIODS) {
        entry[`MA${p}`] = maSeries[p][i]
      }
      return entry
    })
  }, [data, maSeries])

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px]">
      {/* MA toggle row */}
      <div className="flex items-center gap-1.5 px-3 pt-2 pb-0">
        {MA_PERIODS.map(p => (
          <button
            key={p}
            onClick={() => toggleMA(p)}
            className="text-[10px] font-medium px-2 py-0.5 rounded border transition-colors"
            style={{
              borderColor: MA_COLORS[p],
              color: activeMAs.has(p) ? '#fff' : MA_COLORS[p],
              backgroundColor: activeMAs.has(p) ? MA_COLORS[p] : 'transparent',
            }}
          >
            {MA_LABELS[p]}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart
          data={enrichedData}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
          <XAxis
            dataKey="time"
            tick={{ fill: '#5E6673', fontSize: 10 }}
            axisLine={{ stroke: '#EEF0F3' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#5E6673', fontSize: 10 }}
            axisLine={{ stroke: '#EEF0F3' }}
            tickLine={false}
            domain={yDomain}
          />
          <YAxis
            yAxisId="vol"
            orientation="right"
            tick={{ fill: '#5E6673', fontSize: 10 }}
            axisLine={{ stroke: '#EEF0F3' }}
            tickLine={false}
            domain={[0, volMax * 1.1]}
          />
          <Tooltip content={<CandleTooltip />} cursor={{ strokeDasharray: '4 4' }} />
          {/* Volume bars on secondary axis */}
          <Bar
            dataKey="volume"
            yAxisId="vol"
            fill="#e8e8e8"
            opacity={0.5}
            isAnimationActive={false}
            radius={[1, 1, 0, 0]}
          />
          {/* MA lines */}
          {MA_PERIODS.map(p =>
            activeMAs.has(p) ? (
              <Line
                key={`ma${p}`}
                type="monotone"
                dataKey={`MA${p}`}
                stroke={MA_COLORS[p]}
                strokeWidth={1.2}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            ) : null
          )}
          {/* Real OHLC candles rendered via Customized */}
          <Customized component={CandleRenderer} />
          {/* Invisible bar to drive tooltip hover */}
          <Bar
            dataKey="close"
            fill="transparent"
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
