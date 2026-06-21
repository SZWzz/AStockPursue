'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import useSWR, { mutate } from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Bell, Info, AlertTriangle, AlertCircle, Send, Check } from 'lucide-react'

const fetcher = (url: string) => fetch(url).then(r => r.json())

// --------------- helpers ---------------

function levelIcon(level: string) {
  const l = level?.toLowerCase() || ''
  if (l === 'error') return <AlertCircle className="w-4 h-4 text-[var(--down)]" />
  if (l === 'warning') return <AlertTriangle className="w-4 h-4 text-[#F4B000]" />
  return <Info className="w-4 h-4 text-[var(--primary)]" />
}

function levelBadgeVariant(level: string): 'destructive' | 'warning' | 'default' {
  const l = level?.toLowerCase() || ''
  if (l === 'error') return 'destructive'
  if (l === 'warning') return 'warning'
  return 'default'
}

function formatTime(d: string | undefined): string {
  if (!d) return '--'
  const date = new Date(d)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return date.toLocaleDateString()
}

// --------------- Page ---------------

export default function NotificationsPage() {
  const t = useTranslations()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  const { data, error, isLoading } = useSWR('/api/notifications?limit=50', fetcher)

  const notifications: any[] = data?.notifications || data || []
  const unreadCount = notifications.filter((n: any) => !n.read_at).length

  const handleMarkRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await fetch(`/api/notifications/${id}/read`, { method: 'POST' })
      mutate('/api/notifications?limit=50')
    } catch {
      // error handled by SWR
    }
  }

  const handleSendTest = async () => {
    setSending(true)
    try {
      await fetch('/api/notifications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: 'info',
          title: 'Test Notification',
          body: 'This is a test notification from the frontend.',
        }),
      })
      mutate('/api/notifications?limit=50')
    } catch {
      // error handled by SWR
    } finally {
      setSending(false)
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
              {t('notifications.title')}
            </h1>
            {unreadCount > 0 && (
              <Badge variant="destructive" className="text-xs">
                {unreadCount} {t('notifications.unread')}
              </Badge>
            )}
          </div>
          <Button onClick={handleSendTest} disabled={sending} variant="outline" size="sm">
            <Send className="w-4 h-4 mr-2" />
            {t('notifications.sendTest')}
          </Button>
        </div>

        {/* Loading / Error */}
        {isLoading && <p className="text-sm text-[var(--muted-foreground)]">{t('common.loading')}</p>}
        {error && <p className="text-sm text-[var(--down)]">{t('common.error')}</p>}

        {/* Empty state */}
        {!isLoading && !error && notifications.length === 0 && (
          <Card>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-8 text-[var(--muted-foreground)]">
                <Bell className="w-8 h-8 mb-3 opacity-30" />
                <p className="text-sm">{t('notifications.noNotifications')}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Notification list */}
        {notifications.length > 0 && (
          <Card>
            <CardContent>
              <div className="divide-y divide-[var(--border-subtle)]">
                {notifications.map((n: any) => {
                  const isExpanded = expandedId === n.id
                  const isUnread = !n.read_at
                  return (
                    <div
                      key={n.id}
                      className={cn(
                        'py-3 first:pt-0 last:pb-0 cursor-pointer transition-colors',
                        isUnread && 'bg-[var(--primary-muted)]/30 -mx-[var(--card-spacing)] px-[var(--card-spacing)]'
                      )}
                      onClick={() => setExpandedId(isExpanded ? null : n.id)}
                    >
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 mt-0.5">
                          {levelIcon(n.level)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={cn('text-sm font-medium', isUnread && 'font-semibold')}>
                              {n.title}
                            </span>
                            <Badge variant={levelBadgeVariant(n.level)} className="text-[10px] py-0 h-5">
                              {n.level}
                            </Badge>
                          </div>

                          {isExpanded && (
                            <p className="text-sm text-[var(--foreground-secondary)] mt-2 whitespace-pre-wrap">
                              {n.body}
                            </p>
                          )}

                          {!isExpanded && n.body && (
                            <p className="text-xs text-[var(--muted-foreground)] mt-1 truncate">
                              {n.body}
                            </p>
                          )}

                          <div className="flex items-center gap-3 mt-1.5">
                            <span className="text-xs text-[var(--muted-foreground)]">
                              {formatTime(n.created_at)}
                            </span>
                            {isUnread && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 text-xs px-2"
                                onClick={(e) => handleMarkRead(n.id, e)}
                              >
                                <Check className="w-3 h-3 mr-1" />
                                {t('notifications.markRead')}
                              </Button>
                            )}
                          </div>
                        </div>

                        {isUnread && (
                          <div className="shrink-0 w-2 h-2 rounded-full bg-[var(--primary)] mt-1.5" />
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
