// frontend/app/scheduler/page.tsx — Scheduled jobs
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useScheduler } from '@/hooks'
import { cn } from '@/lib/utils'
import { SkeletonTable } from '@/components/ui/SkeletonTable'

interface SchedulerJob {
  id: string
  name: string
  type: string
  schedule: string
  cron?: string
  status: string
  last_run?: string | number
  next_run?: string | number
  duration_ms?: number
  enabled?: boolean
}

// SC2: Convert simple cron to human-readable description
function cronToHuman(cron: string): string {
  if (!cron) return '--'
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5) return cron

  const [min, hour, dom, month, dow] = parts

  const days: Record<string, string> = {
    '0': '周日', '1': '周一', '2': '周二', '3': '周三',
    '4': '周四', '5': '周五', '6': '周六', '7': '周日',
  }

  // "0 9 * * 1-5" → "周一–周五 9:00"
  if (dom === '*' && month === '*' && dow.includes('-')) {
    const [start, end] = dow.split('-')
    const startDay = days[start] || start
    const endDay = days[end] || end
    const h = parseInt(hour)
    const m = parseInt(min)
    const timeStr = m === 0 ? `${h}:00` : `${h}:${String(m).padStart(2, '0')}`
    return `${startDay}–${endDay} ${timeStr}`
  }

  // "0 9 * * 1" → "周一 9:00"
  if (dom === '*' && month === '*' && /^\d$/.test(dow)) {
    const h = parseInt(hour)
    const m = parseInt(min)
    const timeStr = m === 0 ? `${h}:00` : `${h}:${String(m).padStart(2, '0')}`
    return `${days[dow] || dow} ${timeStr}`
  }

  // "0 9 * * *" → "每天 9:00"
  if (dom === '*' && month === '*' && dow === '*') {
    const h = parseInt(hour)
    const m = parseInt(min)
    const timeStr = m === 0 ? `${h}:00` : `${h}:${String(m).padStart(2, '0')}`
    return `每天 ${timeStr}`
  }

  return cron
}

// SC3: Format timestamp for display
function formatTimestamp(ts: string | number | undefined): string {
  if (!ts) return '--'
  const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString()
}

// SC3: Format duration in human-readable form
function formatDuration(ms: number | undefined): string {
  if (ms === undefined || ms === null) return '--'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const mins = Math.floor(ms / 60000)
  const secs = Math.round((ms % 60000) / 1000)
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
}

const JOB_TYPES = ['backtest', 'signal', 'factor', 'screener']

export default function SchedulerPage() {
  const t = useTranslations()
  const { data, isLoading, error, mutate } = useScheduler()

  // SC1: Dialog state for Create Job
  const [dialogOpen, setDialogOpen] = useState(false)
  const [formName, setFormName] = useState('')
  const [formType, setFormType] = useState('backtest')
  const [formCron, setFormCron] = useState('')
  const [formConfig, setFormConfig] = useState('')
  const [creating, setCreating] = useState(false)

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

  // SC1: Handle create job submission
  const handleCreate = async () => {
    if (!formName.trim()) return
    setCreating(true)
    try {
      let configJson: Record<string, unknown> = {}
      try {
        configJson = formConfig.trim() ? JSON.parse(formConfig) : {}
      } catch {
        configJson = {}
      }
      const res = await fetch('/api/scheduler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName.trim(),
          type: formType,
          cron: formCron.trim() || undefined,
          config: configJson,
        }),
      })
      if (res.ok) {
        mutate()
        setDialogOpen(false)
        setFormName('')
        setFormType('backtest')
        setFormCron('')
        setFormConfig('')
      }
    } catch (e) {
      console.error('Failed to create job', e)
    } finally {
      setCreating(false)
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
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.scheduler')}</h1>
          {/* SC1: Create Job button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDialogOpen(true)}
          >
            {t('common.create')}
          </Button>
        </div>

        {/* Content */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
          {isLoading ? (
            <SkeletonTable rows={4} cols={5} />
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
                    <th className="text-left py-2.5 px-4 font-medium">{t('scheduler.jobName')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('scheduler.jobType')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('scheduler.cronExpression')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('trading.status')}</th>
                    {/* SC3: Last Run and Next Run columns */}
                    <th className="text-left py-2.5 px-4 font-medium">{t('scheduler.lastRun')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('scheduler.nextRun')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('scheduler.duration')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">{t('common.actions')}</th>
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
                      <td className="py-2.5 px-4">
                        {/* SC2: Cron with human-readable description */}
                        <div className="text-[13px] font-mono text-[var(--foreground-muted)]">
                          {job.cron || job.schedule || '--'}
                        </div>
                        {(job.cron || job.schedule) && (
                          <div className="text-[11px] text-[var(--foreground-muted)]/70 mt-0.5">
                            {cronToHuman(job.cron || job.schedule || '')}
                          </div>
                        )}
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
                      {/* SC3: Last Run, Next Run, Duration */}
                      <td className="py-2.5 px-4 text-[12px] font-mono text-[var(--foreground-muted)]">
                        {formatTimestamp(job.last_run)}
                      </td>
                      <td className="py-2.5 px-4 text-[12px] font-mono text-[var(--foreground-muted)]">
                        {formatTimestamp(job.next_run)}
                      </td>
                      <td className="py-2.5 px-4 text-[12px] font-mono text-[var(--foreground-muted)]">
                        {formatDuration(job.duration_ms)}
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* SC4: i18n button labels */}
                          {!isRunning(job) && (
                            <button
                              onClick={() => handleAction(job.id, 'start')}
                              className="text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] bg-[var(--up)]/10 text-[var(--up)] hover:bg-[var(--up)]/20 transition-colors"
                            >
                              {t('common.start')}
                            </button>
                          )}
                          {isRunning(job) && (
                            <button
                              onClick={() => handleAction(job.id, 'pause')}
                              className="text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)] hover:bg-[var(--foreground-muted)]/20 transition-colors"
                            >
                              {t('common.pause')}
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

        {/* SC1: Create Job Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{t('scheduler.createJob')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                  {t('scheduler.jobName')}
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder={t('scheduler.jobNamePlaceholder')}
                  className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                  {t('scheduler.jobType')}
                </label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 focus:outline-none focus:border-[var(--primary)]"
                >
                  {JOB_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                  {t('scheduler.cronExpression')}
                </label>
                <input
                  type="text"
                  value={formCron}
                  onChange={(e) => setFormCron(e.target.value)}
                  placeholder={t('scheduler.cronPlaceholder')}
                  className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] font-mono rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                  {t('scheduler.config')}
                </label>
                <textarea
                  value={formConfig}
                  onChange={(e) => setFormConfig(e.target.value)}
                  placeholder={t('scheduler.configPlaceholder')}
                  rows={4}
                  className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] font-mono rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)] resize-none"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                {t('common.cancel')}
              </Button>
              <Button onClick={handleCreate} disabled={creating || !formName.trim()}>
                {creating ? t('common.loading') : t('scheduler.createJob')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </SidebarLayout>
  )
}
