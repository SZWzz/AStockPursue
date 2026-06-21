// frontend/app/broker/page.tsx — Broker accounts
'use client'

import { useState } from 'react'
import useSWR, { mutate } from 'swr'
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
import { cn, formatPrice } from '@/lib/utils'
import { RefreshCw, Plug, PlugZap, Settings } from 'lucide-react'

interface BrokerAccount {
  broker_id: string
  name: string
  status: string
  balance?: number
  currency?: string
  positions_count?: number
  account_id?: string
}

interface BrokerListItem {
  broker_id: string
  name: string
  enabled: boolean
}

export default function BrokerPage() {
  const t = useTranslations()

  const { data: listData, isLoading: listLoading, error: listError, mutate: mutateList } = useSWR(
    '/api/broker/list'
  )

  const { data: accountData, isLoading: accountLoading, error: accountError, mutate: mutateAccount } = useSWR(
    '/api/broker/account'
  )

  // BR2: Credential dialog state
  const [credDialogOpen, setCredDialogOpen] = useState(false)
  const [credBrokerId, setCredBrokerId] = useState('')
  const [credBrokerName, setCredBrokerName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [savingCreds, setSavingCreds] = useState(false)

  // BR3: Refresh state
  const [refreshing, setRefreshing] = useState(false)

  const brokerList: BrokerListItem[] = listData?.data || listData?.brokers || listData || []
  const account: BrokerAccount | null = accountData?.data || accountData || null

  const isLoading = listLoading || accountLoading
  const hasError = listError && accountError

  // BR3: Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await Promise.all([mutateList(), mutateAccount()])
    } finally {
      setRefreshing(false)
    }
  }

  // BR1: Connect/Disconnect toggle
  const handleToggleBroker = async (brokerId: string, enabled: boolean) => {
    try {
      const endpoint = enabled ? `/api/broker/disconnect` : `/api/broker/connect`
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ broker_id: brokerId }),
      })
      mutateList()
      mutateAccount()
    } catch (e) {
      console.error(`Failed to toggle broker ${brokerId}`, e)
    }
  }

  // BR2: Save credentials
  const handleSaveCredentials = async () => {
    setSavingCreds(true)
    try {
      await fetch('/api/broker/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          broker_id: credBrokerId,
          api_key: apiKey,
          api_secret: apiSecret,
        }),
      })
      setCredDialogOpen(false)
      setApiKey('')
      setApiSecret('')
      mutateList()
    } catch (e) {
      console.error('Failed to save credentials', e)
    } finally {
      setSavingCreds(false)
    }
  }

  // BR2: Open credentials dialog
  const openCredDialog = (broker: BrokerListItem) => {
    setCredBrokerId(broker.broker_id)
    setCredBrokerName(broker.name)
    setApiKey('')
    setApiSecret('')
    setCredDialogOpen(true)
  }

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header with refresh button */}
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.broker')}</h1>
          {/* BR3: Refresh button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={cn('w-4 h-4 mr-2', refreshing && 'animate-spin')} />
            {t('common.refresh')}
          </Button>
        </div>

        {/* Loading state */}
        {isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          </Card>
        )}

        {/* Error state */}
        {hasError && !isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {t('common.error')}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={handleRefresh}
              >
                {t('common.retry')}
              </button>
            </div>
          </Card>
        )}

        {/* Broker cards */}
        {!isLoading && !hasError && brokerList.length > 0 && (
          <div className="grid grid-cols-2 gap-[var(--grid-gap)]">
            {brokerList.map((broker) => {
              const isConnected = broker.enabled
              // Merge account data if it matches this broker
              const isActive = account?.broker_id === broker.broker_id || isConnected

              return (
                <Card
                  key={broker.broker_id}
                  className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'inline-block w-2 h-2 rounded-full',
                            isActive ? 'bg-[var(--up)]' : 'bg-[var(--foreground-muted)]'
                          )}
                        />
                        <h3 className="text-[14px] font-semibold text-[var(--foreground)]">{broker.name}</h3>
                      </div>
                      <p className="text-[12px] text-[var(--foreground-muted)] mt-1">
                        {broker.broker_id}
                        {isConnected && (
                          <span className="ml-2 text-[11px] text-[var(--up)]">{t('broker.connected')}</span>
                        )}
                        {!isConnected && (
                          <span className="ml-2 text-[11px] text-[var(--foreground-muted)]">{t('broker.disconnected')}</span>
                        )}
                      </p>
                    </div>

                    {account && account.broker_id === broker.broker_id && (
                      <div className="text-right">
                        <div className="text-[13px] font-mono font-semibold text-[var(--foreground)]">
                          {account.balance !== undefined
                            ? formatPrice(account.balance)
                            : '--'}
                        </div>
                        <div className="text-[11px] text-[var(--foreground-muted)]">
                          {account.currency || 'CNY'}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* BR1 + BR2: Action buttons */}
                  <div className="mt-3 flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className={cn(
                        'text-[11px] h-7 px-2',
                        isConnected
                          ? 'border-[var(--down)]/30 text-[var(--down)] hover:bg-[var(--down)]/10'
                          : 'border-[var(--up)]/30 text-[var(--up)] hover:bg-[var(--up)]/10'
                      )}
                      onClick={() => handleToggleBroker(broker.broker_id, isConnected)}
                    >
                      {isConnected ? (
                        <><PlugZap className="w-3 h-3 mr-1" />{t('common.disconnect')}</>
                      ) : (
                        <><Plug className="w-3 h-3 mr-1" />{t('common.connect')}</>
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-[11px] h-7 px-2"
                      onClick={() => openCredDialog(broker)}
                    >
                      <Settings className="w-3 h-3 mr-1" />
                      {t('common.edit')}
                    </Button>
                  </div>

                  {/* Account details row */}
                  {account && account.broker_id === broker.broker_id && (
                    <div className="mt-3 pt-3 border-t border-[var(--border-subtle)] grid grid-cols-3 gap-2">
                      <div>
                        <div className="text-[11px] text-[var(--foreground-muted)]">{t('broker.account')}</div>
                        <div className="text-[12px] font-mono text-[var(--foreground-secondary)]">
                          {account.account_id || account.broker_id}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-[var(--foreground-muted)]">{t('broker.balance')}</div>
                        <div className="text-[12px] font-mono text-[var(--foreground)]">
                          {account.balance !== undefined
                            ? formatPrice(account.balance)
                            : '--'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-[var(--foreground-muted)]">{t('nav.positions')}</div>
                        <div className="text-[12px] font-mono text-[var(--foreground)]">
                          {account.positions_count ?? '--'}
                        </div>
                      </div>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !hasError && !brokerList.length && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.noData')}</div>
          </Card>
        )}

        {/* BR2: Credentials Dialog */}
        <Dialog open={credDialogOpen} onOpenChange={setCredDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{credBrokerName} - {t('common.edit')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                  {t('broker.apiKey')}
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[var(--foreground-secondary)] mb-1">
                  {t('broker.apiSecret')}
                </label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 placeholder:text-[var(--foreground-muted)] focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCredDialogOpen(false)}>
                {t('common.cancel')}
              </Button>
              <Button onClick={handleSaveCredentials} disabled={savingCreds}>
                {savingCreds ? t('common.loading') : t('broker.saveCredentials')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </SidebarLayout>
  )
}
