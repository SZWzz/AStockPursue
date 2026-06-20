// frontend/app/factors/[id]/page.tsx — Factor detail
'use client'

import { useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { KpiCard } from '@/components/financial/KpiCard'
import { CodeMirror } from '@/components/financial/CodeMirror'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface FactorDetail {
  id: string
  name: string
  formula: string
  description?: string
  status: string
  ic?: number
  ir?: number
  sharpe?: number
  max_drawdown?: number
  turnover?: number
  ic_history?: { date: string; value: number }[]
  created_at?: string | number
}

const STATUS_COLORS: Record<string, string> = {
  production: 'bg-[var(--up)]/10 text-[var(--up)]',
  paper_trading: 'bg-[var(--primary)]/10 text-[var(--primary)]',
  validating: 'bg-[var(--warning)]/10 text-[var(--warning)]',
  discovered: 'bg-[var(--info)]/10 text-[var(--info)]',
  approved: 'bg-[var(--up)]/10 text-[var(--up)]',
  deprecated: 'bg-[var(--down)]/10 text-[var(--down)]',
  archived: 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]',
}

// Simple inline IC chart using SVG — avoids recharts dependency for simple line
function ICChart({ data }: { data: { date: string; value: number }[] }) {
  if (!data.length) {
    return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-8">No IC history available</div>
  }

  const width = 600
  const height = 200
  const padding = { top: 20, right: 20, bottom: 30, left: 50 }
  const plotW = width - padding.left - padding.right
  const plotH = height - padding.top - padding.bottom

  const values = data.map((d) => d.value)
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)
  const yRange = maxVal - minVal || 1

  const xScale = (i: number) => padding.left + (i / Math.max(data.length - 1, 1)) * plotW
  const yScale = (v: number) => padding.top + plotH - ((v - minVal) / yRange) * plotH

  const pathD = data
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i).toFixed(1)} ${yScale(d.value).toFixed(1)}`)
    .join(' ')

  const zeroY = yScale(0)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
      {/* Zero line */}
      <line
        x1={padding.left} y1={zeroY} x2={width - padding.right} y2={zeroY}
        stroke="var(--border-subtle)" strokeWidth={1} strokeDasharray="4 4"
      />
      {/* IC line */}
      <path d={pathD} fill="none" stroke="var(--primary)" strokeWidth={1.5} />
      {/* Y-axis labels */}
      <text x={padding.left - 8} y={padding.top + 4} textAnchor="end" fill="var(--foreground-muted)" fontSize="10" fontFamily="Fira Code, monospace">
        {maxVal.toFixed(2)}
      </text>
      <text x={padding.left - 8} y={padding.top + plotH} textAnchor="end" fill="var(--foreground-muted)" fontSize="10" fontFamily="Fira Code, monospace">
        {minVal.toFixed(2)}
      </text>
    </svg>
  )
}

export default function FactorDetailPage() {
  const t = useTranslations()
  const params = useParams()
  const id = params?.id as string

  const { data, isLoading, error } = useSWR(id ? `/api/factors/${id}` : null, fetcher)

  const detail: FactorDetail | null = data?.data || data || null

  if (isLoading) {
    return (
      <SidebarLayout>
        <div className="flex items-center justify-center h-64 text-[13px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
      </SidebarLayout>
    )
  }

  if (error || !detail) {
    return (
      <SidebarLayout>
        <div className="flex flex-col items-center justify-center h-64 gap-2">
          <div className="text-[13px] text-[var(--down)]">{t('common.error')}</div>
          <button className="text-[13px] underline text-[var(--foreground-secondary)]" onClick={() => window.location.reload()}>
            {t('common.retry')}
          </button>
        </div>
      </SidebarLayout>
    )
  }

  const icData = detail.ic_history || []

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-bold text-[var(--foreground)]">{detail.name}</h1>
            {detail.description && (
              <p className="text-[12px] text-[var(--foreground-muted)] mt-0.5">{detail.description}</p>
            )}
          </div>
          <span className={cn(
            'inline-block text-[11px] font-medium px-2.5 py-1 rounded-[var(--radius-sm)]',
            STATUS_COLORS[detail.status] || 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]'
          )}>
            {detail.status || '--'}
          </span>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-5 gap-[var(--grid-gap)]">
          <KpiCard label="IC" value={detail.ic !== undefined ? detail.ic.toFixed(4) : '--'} />
          <KpiCard label="IR" value={detail.ir !== undefined ? detail.ir.toFixed(2) : '--'} />
          <KpiCard label="Sharpe" value={detail.sharpe !== undefined ? detail.sharpe.toFixed(2) : '--'} />
          <KpiCard label="Max DD" value={detail.max_drawdown !== undefined ? (detail.max_drawdown * 100).toFixed(1) + '%' : '--'} />
          <KpiCard label="Turnover" value={detail.turnover !== undefined ? (detail.turnover * 100).toFixed(1) + '%' : '--'} />
        </div>

        {/* Formula display */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
          <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">Formula</h2>
          <div className="border border-[var(--border-default)] rounded-[var(--radius-sm)] overflow-hidden" style={{ height: 200 }}>
            <CodeMirror value={detail.formula || ''} readOnly={true} language="python" />
          </div>
        </Card>

        {/* IC Chart */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
          <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">IC History</h2>
          <ICChart data={icData} />
        </Card>
      </div>
    </SidebarLayout>
  )
}
