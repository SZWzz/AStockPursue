// frontend/app/workflow/page.tsx — Workflow list
'use client'

import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'
import { cn, formatDateTime } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface Workflow {
  id: string
  name: string
  description?: string
  node_count?: number
  last_run?: string | number
  status: string
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-[var(--up)]/10 text-[var(--up)]',
  running: 'bg-[var(--up)]/10 text-[var(--up)]',
  idle: 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]',
  draft: 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]',
  error: 'bg-[var(--down)]/10 text-[var(--down)]',
  failed: 'bg-[var(--down)]/10 text-[var(--down)]',
}

export default function WorkflowPage() {
  const t = useTranslations()
  const router = useRouter()

  const { data, isLoading, error } = useSWR('/api/workflow', fetcher)
  const workflows: Workflow[] = data?.data || data?.workflows || data || []

  const handleNew = async () => {
    try {
      const res = await fetch('/api/workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: `Workflow ${new Date().toLocaleDateString()}`, dsl: '' }),
      })
      if (res.ok) {
        const result = await res.json()
        const created = result.data || result
        if (created?.id) {
          router.push(`/workflow/${created.id}`)
        }
      }
    } catch (e) {
      console.error('Failed to create workflow', e)
    }
  }

  const handleImport = () => {
    // Placeholder for file import
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.workflow')}</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={handleImport}
              className="border border-[var(--border-default)] text-[var(--foreground-secondary)] text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:text-[var(--foreground)] hover:border-[var(--border-strong)] transition-colors"
            >
              Import
            </button>
            <button
              onClick={handleNew}
              className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity"
            >
              {t('common.create')}
            </button>
          </div>
        </div>

        {/* Content */}
        <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
          {isLoading ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          ) : error ? (
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => window.location.reload()}
              >
                {t('common.retry')}
              </button>
            </div>
          ) : !workflows.length ? (
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                    <th className="text-left py-2.5 px-4 font-medium">Name</th>
                    <th className="text-right py-2.5 px-4 font-medium">Nodes</th>
                    <th className="text-left py-2.5 px-4 font-medium">Last Run</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('trading.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.map((wf) => (
                    <tr
                      key={wf.id}
                      onClick={() => router.push(`/workflow/${wf.id}`)}
                      className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-3)] cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-4 text-[13px] font-medium text-[var(--foreground)]">{wf.name}</td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-muted)] text-right">
                        {wf.node_count ?? '--'}
                      </td>
                      <td className="py-2.5 px-4 text-[13px] font-mono text-[var(--foreground-muted)]">
                        {wf.last_run ? formatDateTime(wf.last_run) : '--'}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className={cn(
                          'inline-block text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]',
                          STATUS_COLORS[wf.status] || 'bg-[var(--foreground-muted)]/10 text-[var(--foreground-muted)]'
                        )}>
                          {wf.status || '--'}
                        </span>
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
