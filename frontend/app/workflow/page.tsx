// frontend/app/workflow/page.tsx — Workflow list
'use client'

import { useState, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import useSWR, { mutate } from 'swr'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { EmptyState } from '@/components/ui/EmptyState'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn, formatDateTime } from '@/lib/utils'
import { Upload } from 'lucide-react'


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

const TEMPLATES: Record<string, { name: string; description: string }> = {
  empty: { name: 'Empty', description: 'Blank canvas' },
  maCross: { name: 'MA Crossover', description: 'Dual moving average crossover strategy' },
  momentum: { name: 'Momentum', description: 'Momentum breakout strategy' },
  meanReversion: { name: 'Mean Reversion', description: 'Bollinger Bands mean reversion' },
  grid: { name: 'Grid Trading', description: 'Price grid trading workflow' },
}

export default function WorkflowPage() {
  const t = useTranslations()
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data, isLoading, error } = useSWR('/api/workflow')
  const workflows: Workflow[] = data?.data || data?.workflows || data || []

  // WL2: Create dialog state
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newTemplate, setNewTemplate] = useState('empty')
  const [creating, setCreating] = useState(false)

  // WL2: handle create with dialog
  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const res = await fetch('/api/workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName.trim(),
          template: newTemplate,
          dsl: '',
        }),
      })
      if (!res.ok) throw new Error('Create failed')
      const result = await res.json()
      const created = result.data || result
      setCreateOpen(false)
      setNewName('')
      setNewTemplate('empty')
      mutate('/api/workflow')
      if (created?.id) {
        router.push(`/workflow/${created.id}`)
      }
    } catch (e) {
      toast.error(t('common.error'))
    } finally {
      setCreating(false)
    }
  }

  // WL1: handle file import via hidden file input
  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const workflowData = JSON.parse(text)
      const res = await fetch('/api/workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflowData),
      })
      if (!res.ok) throw new Error('Import failed')
      mutate('/api/workflow')
      toast.success(t('common.import') + ' ' + t('common.save'))
    } catch {
      toast.error(t('common.error'))
    } finally {
      // reset file input so the same file can be re-imported
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.workflow')}</h1>
          <div className="flex items-center gap-2">
            {/* WL1: Import button with hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              onClick={handleImportClick}
              className="border border-[var(--border-default)] text-[var(--foreground-secondary)] text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:text-[var(--foreground)] hover:border-[var(--border-strong)] transition-colors flex items-center gap-1.5"
            >
              <Upload className="w-3.5 h-3.5" />
              {t('common.import')}
            </button>
            <button
              onClick={() => setCreateOpen(true)}
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
            <EmptyState
              title={t('common.noData')}
              description={t('workflow.emptyHint')}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  {/* WL3: i18n column headers */}
                  <tr className="border-b border-[var(--border-default)] text-[11px] text-[var(--foreground-muted)] uppercase tracking-wider">
                    <th className="text-left py-2.5 px-4 font-medium">{t('workflow.name')}</th>
                    <th className="text-right py-2.5 px-4 font-medium">{t('workflow.nodes')}</th>
                    <th className="text-left py-2.5 px-4 font-medium">{t('workflow.lastRun')}</th>
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

      {/* WL2: Create Workflow Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('workflow.createWorkflow')}</DialogTitle>
            <DialogDescription>{t('workflow.emptyHint')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('workflow.name')}</Label>
              <Input
                placeholder={t('workflow.name')}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('workflow.template')}</Label>
              <Select value={newTemplate} onValueChange={(v) => v && setNewTemplate(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(TEMPLATES).map(([key, tmpl]) => (
                    <SelectItem key={key} value={key}>
                      {tmpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleCreate} disabled={creating || !newName.trim()}>{t('common.create')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SidebarLayout>
  )
}
