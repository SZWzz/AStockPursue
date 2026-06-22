// frontend/components/financial/CorrelationMatrix.tsx
'use client'
import { ScatterChart, Scatter, XAxis, YAxis, ResponsiveContainer } from 'recharts'

const upColor = '#05B169'
const downColor = '#CF202F'
const gridColor = '#EEF0F3'

function correlationColor(v: number): string {
  if (v >= 0) {
    const t = v // 0..1
    return interpolateColor(gridColor, upColor, t)
  }
  const t = -v // 0..1
  return interpolateColor(gridColor, downColor, t)
}

function interpolateColor(a: string, b: string, t: number): string {
  const parse = (hex: string) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]
  const [ar, ag, ab] = parse(a)
  const [br, bg, bb] = parse(b)
  const r = Math.round(ar + (br - ar) * t)
  const g = Math.round(ag + (bg - ag) * t)
  const bl = Math.round(ab + (bb - ab) * t)
  return `rgb(${r},${g},${bl})`
}

interface Props { symbols: string[]; matrix: number[][] }

interface DataPoint {
  x: number
  y: number
  value: number
  label: string
  fill: string
  textFill: string
}

function CustomCell(props: any) {
  const { cx, cy, payload } = props
  if (!payload) return null
  const cellSize = payload.cellSize || 30
  const x = (payload.x || 0) * cellSize + cellSize / 2
  const y = (payload.y || 0) * cellSize + cellSize / 2
  const half = (cellSize - 1) / 2
  return (
    <g>
      <rect
        x={x - half}
        y={y - half}
        width={cellSize - 1}
        height={cellSize - 1}
        fill={payload.fill}
        rx={2}
      />
      <text
        x={x}
        y={y}
        textAnchor="middle"
        dy="0.35em"
        fontSize={Math.max(9, cellSize / 5)}
        fill={payload.textFill}
        fontFamily="var(--font-mono)"
      >
        {payload.label}
      </text>
    </g>
  )
}

export function CorrelationMatrix({ symbols, matrix }: Props) {
  if (!symbols.length || !matrix.length) {
    return (
      <div className="bg-white border border-[var(--border)] rounded-[6px] flex items-center justify-center h-[300px] text-[var(--muted-foreground)]">
        No data
      </div>
    )
  }

  const cellSize = Math.max(20, Math.min(50, 300 / symbols.length))
  const data: DataPoint[] = []
  matrix.forEach((row, i) => {
    row.forEach((v, j) => {
      data.push({
        x: j,
        y: i,
        value: v,
        label: v.toFixed(2),
        fill: correlationColor(v),
        textFill: Math.abs(v) > 0.5 ? '#fff' : '#5E6673',
      })
    })
  })

  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px]">
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart
          margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
        >
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, symbols.length]}
            ticks={symbols.map((_, i) => i + 0.5)}
            tickFormatter={(v: number) => symbols[Math.floor(v)] || ''}
            interval={0}
            tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, symbols.length]}
            ticks={symbols.map((_, i) => i + 0.5)}
            tickFormatter={(v: number) => symbols[Math.floor(v)] || ''}
            interval={0}
            tick={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}
            reversed
            axisLine={false}
            tickLine={false}
          />
          <Scatter
            data={data}
            shape={(props: any) => (
              <CustomCell {...props} payload={{ ...props.payload, cellSize }} />
            )}
            isAnimationActive={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
