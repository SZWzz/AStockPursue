// frontend/app/system/page.tsx — System status
'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { KpiCard } from '@/components/financial/KpiCard'
import { LogViewer } from '@/components/financial/LogViewer'
import { Card } from '@/components/ui/card'
import { useSystemStatus } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { cn } from '@/lib/utils'

interface SystemStatusData {
  uptime?: number
  cpu?: number
  memory?: number
  services?: {
    'go-core'?: string
    'python'?: string
    'pg'?: string
    'redis'?: string
  }
  recent_logs?: string[]
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function ServiceDot({ name, status }: { name: string; status?: string }) {
  const isUp = status === 'up' || status === 'healthy' || status === 'ok' || status === 'running'
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          'inline-block w-2 h-2 rounded-full',
          isUp ? 'bg-[var(--up)]' : 'bg-[var(--down)]'
        )}
      />
      <span className="text-[13px] text-[var(--foreground-secondary)]">{name}</span>
      <span className={cn(
        'text-[11px] font-medium',
        isUp ? 'text-[var(--up)]' : 'text-[var(--down)]'
      )}>
        {isUp ? 'online' : 'offline'}
      </span>
    </div>
  )
}

export default function SystemPage() {
  const t = useTranslations()
  useWebSocket()

  const { data, isLoading, error } = useSystemStatus()
  const [logs, setLogs] = useState<string[]>([])

  const status: SystemStatusData = data?.data || data || {}

  useEffect(() => {
    if (status.recent_logs && status.recent_logs.length > 0) {
      setLogs(status.recent_logs)
    }
  }, [status.recent_logs])

  const services = status.services || {}
  const serviceNames = Object.keys(services).length > 0
    ? Object.entries(services)
    : [
        ['go-core', 'unknown'] as [string, string],
        ['python', 'unknown'] as [string, string],
        ['pg', 'unknown'] as [string, string],
        ['redis', 'unknown'] as [string, string],
      ]

  const cpu = status.cpu ?? 0
  const memory = status.memory ?? 0

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.systemStatus')}</h1>

        {/* Loading state */}
        {isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          </Card>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => window.location.reload()}
              >
                {t('common.retry')}
              </button>
            </div>
          </Card>
        )}

        {!isLoading && !error && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
              <KpiCard
                label="Uptime"
                value={status.uptime !== undefined ? formatUptime(status.uptime) : '--'}
              />
              <KpiCard
                label="CPU"
                value={status.cpu !== undefined ? `${cpu.toFixed(1)}%` : '--'}
                direction={cpu > 80 ? 'down' : cpu > 50 ? 'neutral' : 'up'}
              />
              <KpiCard
                label="Memory"
                value={status.memory !== undefined ? `${memory.toFixed(1)}%` : '--'}
                direction={memory > 80 ? 'down' : memory > 50 ? 'neutral' : 'up'}
              />
              <KpiCard
                label="Services Online"
                value={`${serviceNames.filter(([, s]) => s === 'up' || s === 'healthy' || s === 'ok' || s === 'running').length}/${serviceNames.length}`}
              />
            </div>

            {/* Resource Bars + Service Dots */}
            <div className="grid grid-cols-2 gap-[var(--grid-gap)]">
              {/* CPU / Memory progress bars */}
              <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
                <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-3">Resources</h2>
                <div className="space-y-3">
                  {/* CPU bar */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] text-[var(--foreground-secondary)]">CPU</span>
                      <span className="text-[12px] font-mono text-[var(--foreground-muted)]">{cpu.toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-2 bg-[var(--surface-1)] rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-500',
                          cpu > 80 ? 'bg-[var(--down)]' : cpu > 50 ? 'bg-[var(--warning)]' : 'bg-[var(--up)]'
                        )}
                        style={{ width: `${Math.min(100, cpu)}%` }}
                      />
                    </div>
                  </div>
                  {/* Memory bar */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] text-[var(--foreground-secondary)]">Memory</span>
                      <span className="text-[12px] font-mono text-[var(--foreground-muted)]">{memory.toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-2 bg-[var(--surface-1)] rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-500',
                          memory > 80 ? 'bg-[var(--down)]' : memory > 50 ? 'bg-[var(--warning)]' : 'bg-[var(--up)]'
                        )}
                        style={{ width: `${Math.min(100, memory)}%` }}
                      />
                    </div>
                  </div>
                </div>
              </Card>

              {/* Service Status */}
              <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
                <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-3">Services</h2>
                <div className="space-y-2.5">
                  {serviceNames.map(([name, statusVal]) => (
                    <ServiceDot key={name} name={name} status={statusVal} />
                  ))}
                </div>
              </Card>
            </div>

            {/* Recent Logs */}
            <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
              <h2 className="text-[14px] font-semibold text-[var(--foreground)] mb-2">Recent Logs</h2>
              <LogViewer logs={logs} />
            </Card>
          </>
        )}
      </div>
    </SidebarLayout>
  )
}
