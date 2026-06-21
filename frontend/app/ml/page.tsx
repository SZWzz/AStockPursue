'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import useSWR, { mutate } from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { Plus, Archive, ChevronDown, ChevronRight } from 'lucide-react'

const fetcher = (url: string) => fetch(url).then(r => r.json())

// --------------- helpers ---------------

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

// --------------- Page ---------------

export default function MLModelsPage() {
  const t = useTranslations()
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Build query params
  const params = new URLSearchParams()
  if (category) params.set('category', category)
  if (status) params.set('status', status)
  const qs = params.toString()
  const url = `/api/ml/models${qs ? '?' + qs : ''}`

  const { data, error, isLoading } = useSWR(url, fetcher)

  const models: any[] = data?.models || data || []

  const handleArchive = async (id: string) => {
    if (!confirm(t('ml.archiveConfirm'))) return
    try {
      await fetch(`/api/ml/models/${id}/archive`, { method: 'POST' })
      mutate(url)
    } catch (e) {
      // error handled by SWR
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
            {t('ml.title')}
          </h1>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            {t('ml.createModel')}
          </Button>
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
                    <TableHead className="w-[30px]"></TableHead>
                    <TableHead>{t('ml.name')}</TableHead>
                    <TableHead>{t('ml.modelType')}</TableHead>
                    <TableHead>{t('ml.category')}</TableHead>
                    <TableHead>{t('ml.status')}</TableHead>
                    <TableHead>{t('ml.createdAt')}</TableHead>
                    <TableHead className="w-[80px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((m: any) => (
                    <>
                      <TableRow
                        key={m.id}
                        className="cursor-pointer"
                        onClick={() => setExpandedId(expandedId === m.id ? null : m.id)}
                      >
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
                        <TableCell>
                          {m.status !== 'archived' && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={(e) => { e.stopPropagation(); handleArchive(m.id) }}
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
                          <TableCell colSpan={7} className="bg-[var(--surface-1)]">
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
    </SidebarLayout>
  )
}
