'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import useSWR, { mutate } from 'swr'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
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
import { cn } from '@/lib/utils'
import { Plus, Archive, ChevronDown, ChevronRight, Play, GitCompare } from 'lucide-react'


// --------------- helpers ---------------

interface MLModel {
  id: string
  name: string
  model_type: string
  category: string
  status: string
  created_at?: string
  hyperparams?: Record<string, unknown>
  metrics?: Record<string, number>
  trained_at?: string
  version?: string
  [key: string]: unknown
}

function typeVariant(type: string): 'default' | 'secondary' | 'outline' {
  const t = type?.toLowerCase() || ''
  if (t === 'regression' || t === '回归') return 'default'
  if (t === 'classification' || t === '分类') return 'secondary'
  return 'outline'
}

function statusVariant(status: string): 'success' | 'warning' | 'destructive' | 'secondary' | 'default' {
  const s = status?.toLowerCase() || ''
  if (s === 'ready' || s === '就绪') return 'success'
  if (s === 'training' || s === '训练中') return 'warning'
  if (s === 'failed' || s === '失败') return 'destructive'
  if (s === 'archived' || s === '已归档') return 'secondary'
  return 'default'
}

function formatDate(d: string | undefined): string {
  if (!d) return '--'
  return new Date(d).toLocaleDateString()
}

// --------------- Create Model Dialog ---------------

function CreateModelDialog({
  open,
  onOpenChange,
  t,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  t: (key: string) => string
}) {
  const [name, setName] = useState('')
  const [modelType, setModelType] = useState('regression')
  const [category, setCategory] = useState('factor')
  const [submitting, setSubmitting] = useState(false)

  const handleCreate = async () => {
    if (!name.trim()) return
    setSubmitting(true)
    try {
      await fetch('/api/ml/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), model_type: modelType, category }),
      })
      mutate('/api/ml/models?category=factor&status=ready')
      mutate('/api/ml/models?category=')
      onOpenChange(false)
      setName('')
    } catch (e) {
      // error handled by SWR
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('ml.createModel')}</DialogTitle>
          <DialogDescription>{t('ml.namePlaceholder')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t('ml.name')}</Label>
            <Input
              placeholder={t('ml.namePlaceholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>{t('ml.modelType')}</Label>
            <Select value={modelType} onValueChange={(v) => v && setModelType(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="regression">Regression</SelectItem>
                <SelectItem value="classification">Classification</SelectItem>
                <SelectItem value="ranking">Ranking</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t('ml.category')}</Label>
            <Select value={category} onValueChange={(v) => v && setCategory(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="factor">Factor</SelectItem>
                <SelectItem value="signal">Signal</SelectItem>
                <SelectItem value="risk">Risk</SelectItem>
                <SelectItem value="portfolio">Portfolio</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
          <Button onClick={handleCreate} disabled={submitting || !name.trim()}>{t('common.create')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------- Archive Confirm Dialog ---------------

function ArchiveConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  t,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  t: (key: string) => string
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('ml.archive')}</DialogTitle>
          <DialogDescription>{t('ml.archiveConfirm')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
          <Button variant="destructive" onClick={() => { onConfirm(); onOpenChange(false) }}>{t('common.confirm')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------- Comparison Dialog ---------------

function ComparisonDialog({
  open,
  onOpenChange,
  selectedIds,
  models,
  t,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedIds: string[]
  models: MLModel[]
  t: (key: string) => string
}) {
  const selectedModels = models.filter((m) => selectedIds.includes(m.id))

  if (selectedModels.length < 2) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('ml.comparison')}</DialogTitle>
            <DialogDescription>{t('ml.selectModels')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  }

  // collect all metric keys
  const metricKeys = new Set<string>()
  selectedModels.forEach((m) => {
    if (m.metrics) Object.keys(m.metrics).forEach((k) => metricKeys.add(k))
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[720px]">
        <DialogHeader>
          <DialogTitle>{t('ml.comparison')}</DialogTitle>
          <DialogDescription>{selectedModels.length} {t('ml.selectModels').toLowerCase()}</DialogDescription>
        </DialogHeader>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('ml.metrics')}</TableHead>
                {selectedModels.map((m) => (
                  <TableHead key={m.id} className="text-center">{m.name}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from(metricKeys).map((key) => (
                <TableRow key={key}>
                  <TableCell className="font-medium text-xs">{key}</TableCell>
                  {selectedModels.map((m) => (
                    <TableCell key={m.id} className="text-center font-mono text-xs">
                      {m.metrics?.[key] != null
                        ? typeof m.metrics[key] === 'number'
                          ? Number(m.metrics[key]).toFixed(4)
                          : String(m.metrics[key])
                        : '--'}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------- Page ---------------

export default function MLModelsPage() {
  const t = useTranslations()
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // ML3: archive dialog state
  const [archiveTargetId, setArchiveTargetId] = useState<string | null>(null)
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false)

  // ML1: training state per model
  const [trainingIds, setTrainingIds] = useState<Set<string>>(new Set())

  // ML2: comparison state
  const [selectedModelIds, setSelectedModelIds] = useState<Set<string>>(new Set())
  const [compareDialogOpen, setCompareDialogOpen] = useState(false)

  // Build query params
  const params = new URLSearchParams()
  if (category) params.set('category', category)
  if (status) params.set('status', status)
  const qs = params.toString()
  const url = `/api/ml/models${qs ? '?' + qs : ''}`

  const { data, error, isLoading } = useSWR(url)

  const models: MLModel[] = data?.models || data || []

  // ML3: archive via dialog
  const openArchiveDialog = (id: string) => {
    setArchiveTargetId(id)
    setArchiveDialogOpen(true)
  }

  const handleArchiveConfirm = async () => {
    if (!archiveTargetId) return
    try {
      await fetch(`/api/ml/models/${archiveTargetId}/archive`, { method: 'POST' })
      mutate(url)
    } catch (e) {
      // error handled by SWR
    } finally {
      setArchiveTargetId(null)
    }
  }

  // ML1: train model
  const handleTrain = async (id: string) => {
    setTrainingIds((prev) => new Set(prev).add(id))
    try {
      const res = await fetch(`/api/v1/ml/models/${id}/train`, { method: 'POST' })
      if (!res.ok) throw new Error('Train failed')
      toast.success(t('ml.trainingStarted'))
      mutate(url)
    } catch {
      toast.error(t('common.error'))
    } finally {
      setTrainingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  // ML2: toggle model selection
  const toggleModelSelection = (id: string) => {
    setSelectedModelIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ML2: toggle all/none
  const toggleAllSelection = () => {
    if (selectedModelIds.size === models.length) {
      setSelectedModelIds(new Set())
    } else {
      setSelectedModelIds(new Set(models.map((m: MLModel) => m.id)))
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
            {t('ml.title')}
          </h1>
          <div className="flex items-center gap-2">
            {/* ML2: Compare Selected button */}
            <Button
              variant="outline"
              size="sm"
              disabled={selectedModelIds.size < 2}
              onClick={() => setCompareDialogOpen(true)}
            >
              <GitCompare className="w-4 h-4 mr-2" />
              {t('ml.compareSelected')} ({selectedModelIds.size})
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              {t('ml.createModel')}
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-3">
          <Select value={category} onValueChange={(v) => v != null && setCategory(v)}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={t('ml.allCategories')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">{t('ml.allCategories')}</SelectItem>
              <SelectItem value="factor">Factor</SelectItem>
              <SelectItem value="signal">Signal</SelectItem>
              <SelectItem value="risk">Risk</SelectItem>
              <SelectItem value="portfolio">Portfolio</SelectItem>
            </SelectContent>
          </Select>

          <Select value={status} onValueChange={(v) => v != null && setStatus(v)}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={t('ml.allStatuses')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">{t('ml.allStatuses')}</SelectItem>
              <SelectItem value="ready">{t('ml.ready')}</SelectItem>
              <SelectItem value="training">{t('ml.training')}</SelectItem>
              <SelectItem value="failed">{t('ml.failed')}</SelectItem>
              <SelectItem value="archived">{t('ml.archived')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Loading / Error */}
        {isLoading && <p className="text-sm text-[var(--muted-foreground)]">{t('common.loading')}</p>}
        {error && <p className="text-sm text-[var(--down)]">{t('common.error')}</p>}

        {/* Model list */}
        {!isLoading && !error && models.length === 0 && (
          <p className="text-sm text-[var(--muted-foreground)]">{t('ml.noModels')}</p>
        )}

        {models.length > 0 && (
          <Card>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30px]">
                      {/* ML2: select all checkbox */}
                      <Checkbox
                        checked={selectedModelIds.size === models.length && models.length > 0}
                        onCheckedChange={toggleAllSelection}
                      />
                    </TableHead>
                    <TableHead className="w-[30px]"></TableHead>
                    <TableHead>{t('ml.name')}</TableHead>
                    <TableHead>{t('ml.modelType')}</TableHead>
                    <TableHead>{t('ml.category')}</TableHead>
                    <TableHead>{t('ml.status')}</TableHead>
                    <TableHead>{t('ml.createdAt')}</TableHead>
                    <TableHead className="w-[140px]">{t('common.save')}</TableHead>
                    <TableHead className="w-[80px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((m: MLModel) => (
                    <>
                      <TableRow
                        key={m.id}
                        className="cursor-pointer"
                        onClick={() => setExpandedId(expandedId === m.id ? null : m.id)}
                      >
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {/* ML2: per-row checkbox */}
                          <Checkbox
                            checked={selectedModelIds.has(m.id)}
                            onCheckedChange={() => toggleModelSelection(m.id)}
                          />
                        </TableCell>
                        <TableCell>
                          {expandedId === m.id ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{m.name}</TableCell>
                        <TableCell>
                          <Badge variant={typeVariant(m.model_type)}>{m.model_type}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{m.category}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusVariant(m.status)}>{m.status}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-[var(--muted-foreground)]">
                          {formatDate(m.created_at)}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {/* ML1: Train button */}
                          {m.status !== 'archived' && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleTrain(m.id)}
                              disabled={trainingIds.has(m.id) || m.status === 'training'}
                            >
                              <Play className={cn('w-3 h-3 mr-1', trainingIds.has(m.id) && 'animate-spin')} />
                              {t('ml.train')}
                            </Button>
                          )}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {m.status !== 'archived' && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => openArchiveDialog(m.id)}
                              title={t('ml.archive')}
                            >
                              <Archive className="w-4 h-4" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                      {/* Expanded detail row */}
                      {expandedId === m.id && (
                        <TableRow key={`${m.id}-detail`}>
                          <TableCell colSpan={9} className="bg-[var(--surface-1)]">
                            <div className="grid grid-cols-2 gap-4 py-2">
                              {/* Hyperparams */}
                              <div>
                                <h4 className="text-xs font-semibold text-[var(--muted-foreground)] mb-2">
                                  {t('ml.hyperparams')}
                                </h4>
                                {m.hyperparams ? (
                                  <div className="space-y-1 text-xs">
                                    {Object.entries(m.hyperparams).map(([k, v]) => (
                                      <div key={k} className="flex gap-2">
                                        <span className="text-[var(--muted-foreground)]">{k}:</span>
                                        <span className="font-mono">{String(v)}</span>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-xs text-[var(--muted-foreground)]">--</span>
                                )}
                              </div>
                              {/* Metrics */}
                              <div>
                                <h4 className="text-xs font-semibold text-[var(--muted-foreground)] mb-2">
                                  {t('ml.metrics')}
                                </h4>
                                {m.metrics ? (
                                  <div className="space-y-1 text-xs">
                                    {Object.entries(m.metrics).map(([k, v]) => (
                                      <div key={k} className="flex gap-2">
                                        <span className="text-[var(--muted-foreground)]">{k}:</span>
                                        <span className="font-mono">{typeof v === 'number' ? Number(v).toFixed(4) : String(v)}</span>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-xs text-[var(--muted-foreground)]">--</span>
                                )}
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      <CreateModelDialog open={createOpen} onOpenChange={setCreateOpen} t={t} />

      {/* ML3: Archive Dialog */}
      <ArchiveConfirmDialog
        open={archiveDialogOpen}
        onOpenChange={setArchiveDialogOpen}
        onConfirm={handleArchiveConfirm}
        t={t}
      />

      {/* ML2: Comparison Dialog */}
      <ComparisonDialog
        open={compareDialogOpen}
        onOpenChange={setCompareDialogOpen}
        selectedIds={Array.from(selectedModelIds)}
        models={models}
        t={t}
      />
    </SidebarLayout>
  )
}
