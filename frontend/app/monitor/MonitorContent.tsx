'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { AlertTriangle, CheckCircle, Clock, TrendingDown, TrendingUp, Activity } from 'lucide-react'

interface MetricDef {
  label: string
  key: string
  unit: string
  icon: React.ReactNode
}

interface AlertItem {
  id: string
  level: 'info' | 'warning' | 'error' | 'ok'
  message: string
  timestamp: string
}

const METRICS: MetricDef[] = [
  { label: '当日收益', key: 'daily_pnl', unit: '%', icon: <TrendingUp className="w-4 h-4" /> },
  { label: '累计偏离', key: 'cumulative_deviation', unit: '%', icon: <Activity className="w-4 h-4" /> },
  { label: '因子健康度', key: 'factor_health', unit: 'IC', icon: <CheckCircle className="w-4 h-4" /> },
  { label: '滑点统计', key: 'slippage', unit: '%', icon: <TrendingDown className="w-4 h-4" /> },
  { label: '最大回撤', key: 'max_drawdown', unit: '%', icon: <TrendingDown className="w-4 h-4" /> },
  { label: '持仓数', key: 'position_count', unit: '', icon: <Activity className="w-4 h-4" /> },
]

const fetcher = (url: string) => fetch(url).then(r => r.json())

function formatValue(value: number, unit: string): string {
  if (unit === '%') return value.toFixed(2) + '%'
  if (unit === 'IC') return value.toFixed(4)
  return String(value)
}

function AlertTimeline() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])

  useEffect(() => {
    fetch('/api/v1/monitor/alerts')
      .then(r => r.json())
      .then(data => {
        setAlerts(data.alerts || data || [])
      })
      .catch(() => {
        // fallback empty
      })
  }, [])

  const levelConfig: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
    error: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', icon: <AlertTriangle className="w-3.5 h-3.5 text-red-500" /> },
    warning: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> },
    info: { bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700', icon: <Clock className="w-3.5 h-3.5 text-blue-500" /> },
    ok: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', icon: <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> },
  }

  return (
    <Card className="border-[var(--border-default)]">
      <CardContent className="pt-4 pb-3">
        <h3 className="text-[13px] font-semibold text-[var(--foreground)] mb-3">告警时间线</h3>
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-[12px] text-[var(--foreground-muted)]">
            <CheckCircle className="w-5 h-5 mx-auto mb-1 opacity-40" />
            当前无告警
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.slice(0, 10).map(alert => {
              const config = levelConfig[alert.level] || levelConfig.info
              return (
                <div
                  key={alert.id}
                  className={cn('flex items-start gap-2 rounded-[4px] border px-3 py-2', config.bg)}
                >
                  <div className="shrink-0 mt-0.5">{config.icon}</div>
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-[12px] leading-snug', config.text)}>{alert.message}</p>
                    <span className="text-[10px] text-[var(--foreground-muted)] mt-0.5 block">
                      {alert.timestamp}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function MonitorContent() {
  const { data, isLoading } = useSWR('/api/v1/monitor/health', fetcher, {
    refreshInterval: 10000,
  })

  const health = data?.health || data?.data || data || {}
  const status = data?.status || 'ok'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          系统监控
        </h1>
        <Badge
          variant={status === 'ok' ? 'success' : status === 'warning' ? 'warning' : 'destructive'}
          className="text-[11px]"
        >
          {status === 'ok' ? '正常' : status === 'warning' ? '警告' : '异常'}
        </Badge>
      </div>

      {/* Metric grid 2×3 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {METRICS.map(m => {
          const value = health[m.key]
          return (
            <Card key={m.key} className="border-[var(--border-default)] hover:border-[var(--primary)]/30 transition-colors">
              <CardContent className="pt-4 pb-3 text-center">
                <div className="flex items-center justify-center gap-1.5 text-[12px] text-[var(--foreground-muted)] mb-1">
                  <span className="opacity-60">{m.icon}</span>
                  {m.label}
                </div>
                <div className={cn(
                  'text-[28px] font-mono font-semibold mt-1',
                  isLoading ? 'text-[var(--foreground-muted)] animate-pulse' : 'text-[var(--foreground)]'
                )}>
                  {isLoading ? '--' : value != null ? formatValue(Number(value), m.unit) : '0.00'}
                </div>
                <div className="text-[11px] text-[var(--foreground-secondary)]">{m.unit}</div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Alert Timeline */}
      <AlertTimeline />
    </div>
  )
}
