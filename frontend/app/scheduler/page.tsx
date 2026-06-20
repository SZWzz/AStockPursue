// frontend/app/scheduler/page.tsx — Scheduled jobs
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'
import { useScheduler } from '@/hooks'
import { cn } from '@/lib/utils'

interface SchedulerJob {
  id: string
  name: string
  type: string
  schedule: string
  cron?: string
  status: string
  last_run?: string | number
  next_run?: string | number
  enabled?: boolean
}

export default function SchedulerPage() {
  const t = useTranslations()
  const { data, isLoading, error, mutate } = useScheduler()

  const jobs: SchedulerJob[] = data?.data || data?.jobs || data || []

  const handleAction = async (jobId: string, action: 'start' | 'pause' | 'delete') => {
    try {
      const method = action === 'delete' ? 'DELETE' : 'POST'
      const res = await fetch(`/api/scheduler/${jobId}/${action}`, { method })
      if (res.ok) {
        mutate()
      }
    } catch (e) {
      console.error(`Failed to ${action} job ${jobId}`, e)
    }
  }

  const isRunning = (job: SchedulerJob) =>
    job.status === 'running' || job.status === 'active' || job.enabled === true

  const isPaused = (job: SchedulerJob) =>
    job.status === 'paused' || job.status === 'stopped' || job.enabled === false

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.scheduler')}</h1>

        {/* Content */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
          {isLoading ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          ) : error ? (
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => mutate()}
              >
                {t('common.retry')}
              </button>
            </div>
          ) : !jobs.length ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                    <th className="text-left py-2.5 px-4 font-medium">Job Name</th>
                    <th className="text-left py-2.5 px-4 font-medium">Type</th>
                    <th className="text-left py-2.5 px-4 font-medium">Schedule</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('trading.status')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-3)] transition-colors"
                    >
                      <td className="py-2.5 px-4 text-[13px] font-medium text-[var(--foreground)]">{job.name}</td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-secondary)]">
                        {job.type || '--'}
                      </td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-muted)]">
                        {job.cron || job.schedule || '--'}
                      </td>
                      <td className="py-2.5 px-4">
                        <span
                          className={cn(
                            'inline-block text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]',
                            isRunning(job)
                              ? 'bg-[var(--up)]/10 text-[var(--up)]'
                              : isPaused(job)
                              ? 'bg-[var(--down)]/10 text-[var(--down)]'
                              : 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]'
                          )}
                        >
                          {job.status || (job.enabled ? 'active' : 'paused')}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {!isRunning(job) && (
                            <button
                              onClick={() => handleAction(job.id, 'start')}
                              className="text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] bg-[var(--up)]/10 text-[var(--up)] hover:bg-[var(--up)]/20 transition-colors"
                            >
                              Start
                            </button>
                          )}
                          {isRunning(job) && (
                            <button
                              onClick={() => handleAction(job.id, 'pause')}
                              className="text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)] hover:bg-[var(--foreground-muted)]/20 transition-colors"
                            >
                              Pause
                            </button>
                          )}
                          <button
                            onClick={() => {
                              if (confirm(t('common.confirmDelete'))) {
                                handleAction(job.id, 'delete')
                              }
                            }}
                            className="text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] bg-[var(--down)]/10 text-[var(--down)] hover:bg-[var(--down)]/20 transition-colors"
                          >
                            {t('common.delete')}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </SidebarLayout>
  )
}
