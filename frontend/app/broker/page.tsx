// frontend/app/broker/page.tsx — Broker accounts
'use client'

import useSWR from 'swr'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'
import { cn, formatPrice } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

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

  const { data: listData, isLoading: listLoading, error: listError } = useSWR(
    '/api/broker/list',
    fetcher
  )

  const { data: accountData, isLoading: accountLoading, error: accountError } = useSWR(
    '/api/broker/account',
    fetcher
  )

  const brokerList: BrokerListItem[] = listData?.data || listData?.brokers || listData || []
  const account: BrokerAccount | null = accountData?.data || accountData || null

  const isLoading = listLoading || accountLoading
  const hasError = listError && accountError

  return (
    <SidebarLayout>
      <div className="space-y-3">
        {/* Header */}
        <h1 className="text-[20px] font-bold text-[var(--foreground)]">{t('nav.broker')}</h1>

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
                onClick={() => window.location.reload()}
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
                          <span className="ml-2 text-[11px] text-[var(--up)]">Connected</span>
                        )}
                        {!isConnected && (
                          <span className="ml-2 text-[11px] text-[var(--foreground-muted)]">Disabled</span>
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

                  {/* Account details row */}
                  {account && account.broker_id === broker.broker_id && (
                    <div className="mt-3 pt-3 border-t border-[var(--border-subtle)] grid grid-cols-3 gap-2">
                      <div>
                        <div className="text-[11px] text-[var(--foreground-muted)]">Account</div>
                        <div className="text-[12px] font-mono text-[var(--foreground-secondary)]">
                          {account.account_id || account.broker_id}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-[var(--foreground-muted)]">Balance</div>
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
      </div>
    </SidebarLayout>
  )
}
