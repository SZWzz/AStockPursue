// frontend/app/settings/page.tsx — Unified settings with 7 tabs (Coinbase theme)
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from 'sonner'
import { Eye, EyeOff, Link, Save, RotateCcw } from 'lucide-react'

// ---- Types ----

interface GeneralSettings {
  language: string
  theme: string
  default_market: string
  default_freq: string
  default_symbols: string[]
}

interface RiskSettings {
  max_position_pct: number
  stop_loss_pct: number
  take_profit_pct: number
  trailing_stop_pct: number
  daily_loss_limit: number
  max_position_count: number
}

interface DataSourceRow {
  key: string
  label: string
  value: string
  masked: boolean
}

interface LLMSettings {
  provider: string
  model: string
  api_key: string
  base_url: string
}

interface BrokerCredential {
  id?: string
  exchange: string
  label: string
  api_key: string
  secret_key: string
  passphrase: string
  testnet: boolean
  active: boolean
}

interface NotifSettings {
  enabled: boolean
  telegram_bot_token: string
  telegram_chat_id: string
  email_smtp_host: string
  email_smtp_port: number
  email_username: string
  email_password: string
  email_from: string
  webhook_url: string
  alert_on_error: boolean
  alert_on_trade: boolean
  daily_summary: boolean
}

interface AccountSettings {
  email: string
}

// ---- Constants ----

const EXCHANGES = ['binance', 'okx', 'futu']
const LLM_PROVIDERS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  azure: ['gpt-4', 'gpt-4-32k'],
  anthropic: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
  local: ['llama-3-70b', 'mixtral-8x7b'],
}
const DATA_SOURCE_KEYS = [
  { key: 'tushare', label: 'Tushare Token' },
  { key: 'twelvedata', label: 'Twelve Data API Key' },
  { key: 'finnhub', label: 'Finnhub API Key' },
  { key: 'tiingo', label: 'Tiingo API Key' },
]
const FREQUENCIES = [
  { value: '1m', label: '1min' }, { value: '5m', label: '5min' },
  { value: '15m', label: '15min' }, { value: '30m', label: '30min' },
  { value: '1h', label: '1h' }, { value: '4h', label: '4h' },
  { value: '1d', label: 'Daily' }, { value: '1w', label: 'Weekly' },
]
const MARKETS = [
  { value: 'cn', label: 'China A-Share' },
  { value: 'hk', label: 'Hong Kong' },
  { value: 'us', label: 'US' },
  { value: 'crypto', label: 'Crypto' },
]

// ---- Component ----

export default function SettingsPage() {
  const t = useTranslations()
  const [loading, setLoading] = useState(true)
  const [savingTab, setSavingTab] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('general')

  // General
  const [general, setGeneral] = useState<GeneralSettings>({
    language: 'zh', theme: 'compact', default_market: 'cn', default_freq: '1d', default_symbols: ['000300.SH'],
  })
  const [symbolInput, setSymbolInput] = useState('')

  // Risk
  const [risk, setRisk] = useState<RiskSettings>({
    max_position_pct: 20, stop_loss_pct: 5, take_profit_pct: 10,
    trailing_stop_pct: 0, daily_loss_limit: 10000, max_position_count: 10,
  })

  // Data sources
  const [dataSources, setDataSources] = useState<DataSourceRow[]>(
    DATA_SOURCE_KEYS.map(d => ({ ...d, value: '', masked: true }))
  )

  // LLM
  const [llm, setLLM] = useState<LLMSettings>({
    provider: 'openai', model: 'gpt-4o-mini', api_key: '', base_url: '',
  })
  const [llmKeyMasked, setLLMKeyMasked] = useState(true)

  // Brokers
  const [brokers, setBrokers] = useState<BrokerCredential[]>([])
  const [editingBroker, setEditingBroker] = useState<BrokerCredential | null>(null)
  const [showBrokerForm, setShowBrokerForm] = useState(false)

  // Notifications
  const [notif, setNotif] = useState<NotifSettings>({
    enabled: true, telegram_bot_token: '', telegram_chat_id: '',
    email_smtp_host: '', email_smtp_port: 587, email_username: '', email_password: '',
    email_from: '', webhook_url: '', alert_on_error: true, alert_on_trade: false, daily_summary: false,
  })

  // Account
  const [account, setAccount] = useState<AccountSettings>({ email: '' })
  const [passwordForm, setPasswordForm] = useState({ current: '', new_: '', confirm: '' })

  // ---- Load settings ----
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(d => {
        const s = d.data || d.settings || d
        if (s.general) {
          setGeneral(prev => ({ ...prev, ...s.general }))
        } else {
          // Flat format fallback
          if (s.language) setGeneral(prev => ({ ...prev, language: s.language }))
          if (s.theme) setGeneral(prev => ({ ...prev, theme: s.theme }))
          if (s.default_market) setGeneral(prev => ({ ...prev, default_market: s.default_market }))
          if (s.default_freq) setGeneral(prev => ({ ...prev, default_freq: s.default_freq }))
          if (s.default_symbols) setGeneral(prev => ({ ...prev, default_symbols: s.default_symbols }))
        }
        if (s.risk_limits) setRisk(prev => ({ ...prev, ...s.risk_limits }))
        if (s.data_sources) {
          setDataSources(prev => prev.map(ds => ({
            ...ds, value: s.data_sources[ds.key] || '', masked: true,
          })))
        }
        if (s.llm) setLLM(prev => ({ ...prev, ...s.llm }))
        if (s.brokers) setBrokers(s.brokers)
        if (s.notifications) setNotif(prev => ({ ...prev, ...s.notifications }))
        if (s.account) setAccount(prev => ({ ...prev, ...s.account }))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // ---- Save helpers ----
  const saveSection = useCallback(async (section: string, data: any) => {
    setSavingTab(section)
    try {
      const full = { general, risk_limits: risk, data_sources: Object.fromEntries(dataSources.map(d => [d.key, d.value])), llm, brokers, notifications: notif, account }
      ;(full as any)[section] = data
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(full),
      })
      if (res.ok) {
        toast.success(t('settings.settingsSaved'))
      } else {
        toast.error(t('common.error'))
      }
    } catch {
      toast.error(t('common.error'))
    } finally {
      setSavingTab(null)
    }
  }, [general, risk, dataSources, llm, brokers, notif, account, t])

  // ---- Toggle helpers ----
  const Toggle = ({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
        checked ? 'bg-[var(--primary)]' : 'bg-[var(--surface-3)]'
      }`}
    >
      <span className={`pointer-events-none block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${
        checked ? 'translate-x-4' : 'translate-x-0'
      }`} />
    </button>
  )

  // ---- Password masked input ----
  const PasswordField = ({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) => {
    const [visible, setVisible] = useState(false)
    return (
      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-[var(--foreground-muted)]">{label}</label>
        <div className="relative">
          <Input
            type={visible ? 'text' : 'password'}
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={placeholder || '••••••••'}
            className="h-9 text-[13px] pr-8"
          />
          <button type="button" onClick={() => setVisible(!visible)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] hover:text-[var(--foreground)]">
            {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    )
  }

  // ---- Render ----
  if (loading) return (
    <SidebarLayout>
      <div className="flex items-center justify-center h-64 text-[13px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
    </SidebarLayout>
  )

  return (
    <SidebarLayout>
      <div className="space-y-3">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">{t('nav.settings')}</h1>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full justify-start border-b border-[var(--border)] rounded-none bg-transparent p-0 h-auto gap-0 overflow-x-auto">
            {['general','risk','dataSources','llm','brokers','notifications','account'].map(k => (
              <TabsTrigger
                key={k}
                value={k}
                className="text-[13px] px-4 py-2.5 border-b-2 border-transparent data-[state=active]:border-[var(--primary)] data-[state=active]:text-[var(--primary)] data-[state=active]:shadow-none rounded-none bg-transparent hover:text-[var(--foreground)] shrink-0"
              >
                {t(`settings.${k}`)}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className="pt-4">
            {/* ---- Tab 1: General ---- */}
            <TabsContent value="general" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  <FormRow label={t('settings.language')}>
                    <Select value={general.language} onValueChange={(v) => { if (v) setGeneral(p => ({ ...p, language: v })) }}>
                      <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="zh">中文</SelectItem>
                        <SelectItem value="en">English</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormRow>
                  <FormRow label={t('settings.theme')}>
                    <Select value={general.theme} onValueChange={(v) => { if (v) setGeneral(p => ({ ...p, theme: v })) }}>
                      <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="compact">Compact</SelectItem>
                        <SelectItem value="standard">Standard</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormRow>
                  <FormRow label={t('settings.defaultMarket')}>
                    <Select value={general.default_market} onValueChange={(v) => { if (v) setGeneral(p => ({ ...p, default_market: v })) }}>
                      <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {MARKETS.map(m => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </FormRow>
                  <FormRow label={t('settings.defaultFreq')}>
                    <Select value={general.default_freq} onValueChange={(v) => { if (v) setGeneral(p => ({ ...p, default_freq: v })) }}>
                      <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {FREQUENCIES.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </FormRow>
                  <FormRow label={t('settings.defaultSymbols')}>
                    <div>
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {general.default_symbols.map((s, i) => (
                          <Badge key={i} variant="secondary" className="text-[12px] font-mono gap-1 pr-1">
                            {s}
                            <button onClick={() => setGeneral(p => ({ ...p, default_symbols: p.default_symbols.filter((_, j) => j !== i) }))} className="ml-0.5 hover:text-[var(--destructive)]">&times;</button>
                          </Badge>
                        ))}
                      </div>
                      <div className="flex gap-2">
                        <Input
                          value={symbolInput}
                          onChange={e => setSymbolInput(e.target.value.toUpperCase())}
                          onKeyDown={e => {
                            if (e.key === 'Enter' && symbolInput.trim()) {
                              e.preventDefault()
                              setGeneral(p => ({ ...p, default_symbols: [...p.default_symbols, symbolInput.trim()] }))
                              setSymbolInput('')
                            }
                          }}
                          placeholder="000300.SH"
                          className="h-9 text-[13px] flex-1"
                        />
                        <Button variant="outline" size="sm" onClick={() => {
                          if (symbolInput.trim()) {
                            setGeneral(p => ({ ...p, default_symbols: [...p.default_symbols, symbolInput.trim()] }))
                            setSymbolInput('')
                          }
                        }} className="h-9">{t('common.create')}</Button>
                      </div>
                    </div>
                  </FormRow>
                  <Button onClick={() => saveSection('general', general)} disabled={savingTab === 'general'} size="sm">
                    <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'general' ? t('common.saving') : t('common.save')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ---- Tab 2: Risk Limits ---- */}
            <TabsContent value="risk" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  <FormRow label={t('settings.maxPositionPct')}>
                    <SliderField value={risk.max_position_pct} onChange={v => setRisk(p => ({ ...p, max_position_pct: v }))} max={100} unit="%" />
                  </FormRow>
                  <FormRow label={t('settings.stopLossPct')}>
                    <SliderField value={risk.stop_loss_pct} onChange={v => setRisk(p => ({ ...p, stop_loss_pct: v }))} max={50} unit="%" />
                  </FormRow>
                  <FormRow label={t('settings.takeProfitPct')}>
                    <SliderField value={risk.take_profit_pct} onChange={v => setRisk(p => ({ ...p, take_profit_pct: v }))} max={100} unit="%" />
                  </FormRow>
                  <FormRow label={t('settings.trailingStopPct')}>
                    <SliderField value={risk.trailing_stop_pct} onChange={v => setRisk(p => ({ ...p, trailing_stop_pct: v }))} max={50} unit="%" />
                  </FormRow>
                  <FormRow label={t('settings.dailyLossLimit')}>
                    <Input type="number" value={risk.daily_loss_limit} onChange={e => setRisk(p => ({ ...p, daily_loss_limit: Number(e.target.value) }))} className="h-10 text-[13px] w-full" />
                  </FormRow>
                  <FormRow label={t('settings.maxPositionCount')}>
                    <Input type="number" value={risk.max_position_count} onChange={e => setRisk(p => ({ ...p, max_position_count: Number(e.target.value) }))} min={1} max={100} className="h-10 text-[13px] w-full" />
                  </FormRow>
                  <Button onClick={() => saveSection('risk_limits', risk)} disabled={savingTab === 'risk'} size="sm">
                    <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'risk' ? t('common.saving') : t('common.save')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ---- Tab 3: Data Sources ---- */}
            <TabsContent value="dataSources" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  {dataSources.map((ds, i) => (
                    <div key={ds.key}>
                      <PasswordField
                        label={ds.label}
                        value={ds.value}
                        onChange={v => setDataSources(prev => prev.map((d, j) => j === i ? { ...d, value: v } : d))}
                      />
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            const res = await fetch('/api/analysis/test-data-source', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ provider: ds.key, api_key: ds.value }),
                            })
                            if (res.ok) {
                              toast.success(t('settings.testSuccess'))
                            } else {
                              toast.error(t('common.error'))
                            }
                          } catch {
                            toast.error(t('common.error'))
                          }
                        }}
                        className="text-[11px] text-[var(--primary)] hover:underline mt-1"
                      >
                        {t('settings.testConnection')}
                      </button>
                    </div>
                  ))}
                  <Button onClick={() => saveSection('data_sources', Object.fromEntries(dataSources.map(d => [d.key, d.value])))} disabled={savingTab === 'dataSources'} size="sm">
                    <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'dataSources' ? t('common.saving') : t('common.save')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ---- Tab 4: LLM ---- */}
            <TabsContent value="llm" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  <FormRow label={t('settings.llmProvider')}>
                    <Select value={llm.provider} onValueChange={(v) => { if (v) setLLM(p => ({ ...p, provider: v, model: (LLM_PROVIDERS as any)[v]?.[0] || '' })) }}>
                      <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="azure">Azure</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                        <SelectItem value="local">Local</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormRow>
                  <FormRow label={t('settings.llmModel')}>
                    <Select value={llm.model} onValueChange={(v) => { if (v) setLLM(p => ({ ...p, model: v })) }}>
                      <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {(LLM_PROVIDERS[llm.provider] || []).map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </FormRow>
                  <PasswordField label={t('settings.llmApiKey')} value={llm.api_key} onChange={v => setLLM(p => ({ ...p, api_key: v }))} />
                  <FormRow label={t('settings.llmBaseUrl')}>
                    <Input value={llm.base_url} onChange={e => setLLM(p => ({ ...p, base_url: e.target.value }))} placeholder="https://api.openai.com/v1" className="h-10 text-[13px] w-full" />
                  </FormRow>
                  <div className="flex gap-2">
                    <Button onClick={() => saveSection('llm', llm)} disabled={savingTab === 'llm'} size="sm">
                      <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'llm' ? t('common.saving') : t('common.save')}
                    </Button>
                    <Button variant="outline" size="sm" onClick={async () => {
                      try {
                        const res = await fetch('/api/analysis/test-llm', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ provider: llm.provider, model: llm.model, api_key: llm.api_key, base_url: llm.base_url }),
                        })
                        if (res.ok) {
                          toast.success(t('settings.testSuccess'))
                        } else {
                          toast.error(t('common.error'))
                        }
                      } catch {
                        toast.error(t('common.error'))
                      }
                    }}>{t('settings.testConnection')}</Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ---- Tab 5: Brokers ---- */}
            <TabsContent value="brokers" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  {brokers.length === 0 ? (
                    <div className="text-[13px] text-[var(--foreground-muted)] text-center py-8">
                      {t('settings.noBrokers')}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {brokers.map((b, i) => (
                        <div key={b.id || i} className="flex items-center justify-between p-3 border border-[var(--border)] rounded-[6px] bg-[var(--surface-1)]">
                          <div className="flex items-center gap-3">
                            <Badge variant="outline" className="font-mono text-[11px]">{b.exchange}</Badge>
                            <span className="text-[13px] font-medium">{b.label || b.exchange}</span>
                            <div className="flex items-center gap-2 text-[11px]">
                              <label className="flex items-center gap-1 text-[var(--foreground-muted)]">
                                <Toggle checked={b.testnet} onChange={() => setBrokers(prev => prev.map((br, j) => j === i ? { ...br, testnet: !br.testnet } : br))} />
                                {t('settings.brokerTestnet')}
                              </label>
                              <label className="flex items-center gap-1 text-[var(--foreground-muted)]">
                                <Toggle checked={b.active} onChange={() => setBrokers(prev => prev.map((br, j) => j === i ? { ...br, active: !br.active } : br))} />
                                {t('settings.brokerActive')}
                              </label>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="sm" className="h-7 text-[11px]" onClick={() => { setEditingBroker(b); setShowBrokerForm(true) }}>{t('common.edit')}</Button>
                            <Button variant="ghost" size="sm" className="h-7 text-[11px] text-[var(--down)]" onClick={() => setBrokers(prev => prev.filter((_, j) => j !== i))}>{t('common.delete')}</Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <Button variant="outline" size="sm" onClick={() => { setEditingBroker({ exchange: 'binance', label: '', api_key: '', secret_key: '', passphrase: '', testnet: true, active: true }); setShowBrokerForm(true) }}>
                    {t('settings.addCredential')}
                  </Button>

                  {showBrokerForm && editingBroker && (
                    <BrokerFormDialog
                      broker={editingBroker}
                      onSave={(b) => {
                        if (b.id) {
                          setBrokers(prev => prev.map(br => br.id === b.id ? b : br))
                        } else {
                          setBrokers(prev => [...prev, { ...b, id: `broker-${Date.now()}` }])
                        }
                        setShowBrokerForm(false)
                        setEditingBroker(null)
                      }}
                      onCancel={() => { setShowBrokerForm(false); setEditingBroker(null) }}
                      t={t}
                    />
                  )}

                  <Button onClick={() => saveSection('brokers', brokers)} disabled={savingTab === 'brokers'} size="sm">
                    <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'brokers' ? t('common.saving') : t('common.save')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ---- Tab 6: Notifications ---- */}
            <TabsContent value="notifications" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  <FormRow label={t('settings.notificationsEnabled')}>
                    <Toggle checked={notif.enabled} onChange={v => setNotif(p => ({ ...p, enabled: v }))} />
                  </FormRow>
                  <div className="border-t border-[var(--border)] pt-4">
                    <h3 className="text-[14px] font-semibold mb-3">{t('settings.telegram')}</h3>
                    <div className="space-y-3">
                      <PasswordField label={t('settings.telegramBotToken')} value={notif.telegram_bot_token} onChange={v => setNotif(p => ({ ...p, telegram_bot_token: v }))} />
                      <FormRow label={t('settings.telegramChatId')}>
                        <Input value={notif.telegram_chat_id} onChange={e => setNotif(p => ({ ...p, telegram_chat_id: e.target.value }))} className="h-10 text-[13px] w-full" />
                      </FormRow>
                      <Button variant="outline" size="sm" onClick={async () => {
                        try {
                          const res = await fetch('/api/notifications/test-telegram', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ bot_token: notif.telegram_bot_token, chat_id: notif.telegram_chat_id }),
                          })
                          if (res.ok) {
                            toast.success(t('settings.testSuccess'))
                          } else {
                            toast.error(t('common.error'))
                          }
                        } catch {
                          toast.error(t('common.error'))
                        }
                      }}>{t('settings.testConnection')}</Button>
                    </div>
                  </div>
                  <div className="border-t border-[var(--border)] pt-4">
                    <h3 className="text-[14px] font-semibold mb-3">{t('settings.emailSection')}</h3>
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <FormRow label={t('settings.emailSmtpHost')}>
                          <Input value={notif.email_smtp_host} onChange={e => setNotif(p => ({ ...p, email_smtp_host: e.target.value }))} className="h-10 text-[13px]" />
                        </FormRow>
                        <FormRow label={t('settings.emailSmtpPort')}>
                          <Input type="number" value={notif.email_smtp_port} onChange={e => setNotif(p => ({ ...p, email_smtp_port: Number(e.target.value) }))} className="h-10 text-[13px]" />
                        </FormRow>
                      </div>
                      <FormRow label={t('settings.emailUsername')}>
                        <Input value={notif.email_username} onChange={e => setNotif(p => ({ ...p, email_username: e.target.value }))} className="h-10 text-[13px] w-full" />
                      </FormRow>
                      <PasswordField label={t('settings.emailPassword')} value={notif.email_password} onChange={v => setNotif(p => ({ ...p, email_password: v }))} />
                      <FormRow label={t('settings.emailFrom')}>
                        <Input value={notif.email_from} onChange={e => setNotif(p => ({ ...p, email_from: e.target.value }))} className="h-10 text-[13px] w-full" />
                      </FormRow>
                      <Button variant="outline" size="sm" onClick={async () => {
                        try {
                          const res = await fetch('/api/notifications/test-email', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ smtp_host: notif.email_smtp_host, smtp_port: notif.email_smtp_port, username: notif.email_username, password: notif.email_password, from: notif.email_from, to: account.email }),
                          })
                          if (res.ok) {
                            toast.success(t('settings.testSuccess'))
                          } else {
                            toast.error(t('common.error'))
                          }
                        } catch {
                          toast.error(t('common.error'))
                        }
                      }}>{t('settings.testConnection')}</Button>
                    </div>
                  </div>
                  <div className="border-t border-[var(--border)] pt-4">
                    <h3 className="text-[14px] font-semibold mb-3">{t('settings.webhook')}</h3>
                    <FormRow label={t('settings.webhookUrl')}>
                      <Input value={notif.webhook_url} onChange={e => setNotif(p => ({ ...p, webhook_url: e.target.value }))} className="h-10 text-[13px] w-full" />
                    </FormRow>
                  </div>
                  <div className="border-t border-[var(--border)] pt-4 space-y-3">
                    <h3 className="text-[14px] font-semibold mb-3">{t('settings.alerts')}</h3>
                    <FormRow label={t('settings.alertOnError')}>
                      <Toggle checked={notif.alert_on_error} onChange={v => setNotif(p => ({ ...p, alert_on_error: v }))} />
                    </FormRow>
                    <FormRow label={t('settings.alertOnTrade')}>
                      <Toggle checked={notif.alert_on_trade} onChange={v => setNotif(p => ({ ...p, alert_on_trade: v }))} />
                    </FormRow>
                    <FormRow label={t('settings.dailySummary')}>
                      <Toggle checked={notif.daily_summary} onChange={v => setNotif(p => ({ ...p, daily_summary: v }))} />
                    </FormRow>
                  </div>
                  <Button onClick={() => saveSection('notifications', notif)} disabled={savingTab === 'notifications'} size="sm">
                    <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'notifications' ? t('common.saving') : t('common.save')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ---- Tab 7: Account ---- */}
            <TabsContent value="account" className="mt-0 space-y-4">
              <Card>
                <CardContent className="pt-4 space-y-4">
                  <FormRow label={t('settings.username')}>
                    <Input value="admin" readOnly className="h-10 text-[13px] w-full bg-[var(--surface-1)]" />
                  </FormRow>
                  <FormRow label={t('settings.email')}>
                    <Input value={account.email} onChange={e => setAccount(p => ({ ...p, email: e.target.value }))} className="h-10 text-[13px] w-full" />
                  </FormRow>
                  <div className="border-t border-[var(--border)] pt-4 space-y-3">
                    <h3 className="text-[14px] font-semibold">{t('settings.changePassword')}</h3>
                    <PasswordField label={t('settings.currentPassword')} value={passwordForm.current} onChange={v => setPasswordForm(p => ({ ...p, current: v }))} />
                    <PasswordField label={t('settings.newPassword')} value={passwordForm.new_} onChange={v => setPasswordForm(p => ({ ...p, new_: v }))} />
                    <PasswordField label={t('settings.confirmPassword')} value={passwordForm.confirm} onChange={v => setPasswordForm(p => ({ ...p, confirm: v }))} />
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={() => saveSection('account', account)} disabled={savingTab === 'account'} size="sm">
                      <Save className="w-3.5 h-3.5 mr-1.5" />{savingTab === 'account' ? t('common.saving') : t('common.save')}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => toast.success(t('settings.settingsSaved'))}>
                      <RotateCcw className="w-3.5 h-3.5 mr-1.5" />{t('settings.resetToDefaults')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </SidebarLayout>
  )
}

// ---- Sub-components ----

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[11px] font-medium text-[var(--foreground-muted)]">{label}</label>
      {children}
    </div>
  )
}

function SliderField({ value, onChange, max, unit }: { value: number; onChange: (v: number) => void; max: number; unit: string }) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range" min={0} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="flex-1 h-1.5 appearance-none bg-[var(--surface-3)] rounded-full accent-[var(--primary)] cursor-pointer"
      />
      <Input
        type="number" value={value} min={0} max={max}
        onChange={e => onChange(Number(e.target.value))}
        className="w-20 h-9 text-[13px] text-center font-mono"
      />
      <span className="text-[11px] text-[var(--foreground-muted)] w-6">{unit}</span>
    </div>
  )
}

function BrokerFormDialog({ broker, onSave, onCancel, t }: { broker: BrokerCredential; onSave: (b: BrokerCredential) => void; onCancel: () => void; t: any }) {
  const [form, setForm] = useState<BrokerCredential>({ ...broker })
  const isOKX = form.exchange === 'okx'
  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={onCancel}>
      <div className="bg-white rounded-[8px] p-6 w-[400px] max-h-[80vh] overflow-y-auto shadow-xl border border-[var(--border)]" onClick={e => e.stopPropagation()}>
        <h3 className="text-[16px] font-semibold mb-4">{broker.id ? t('common.edit') : t('settings.addCredential')}</h3>
        <div className="space-y-3">
          <FormRow label={t('settings.brokerExchange')}>
            <Select value={form.exchange} onValueChange={(v) => { if (v) setForm(p => ({ ...p, exchange: v })) }}>
              <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
              <SelectContent>
                {EXCHANGES.map(e => <SelectItem key={e} value={e}>{e.toUpperCase()}</SelectItem>)}
              </SelectContent>
            </Select>
          </FormRow>
          <FormRow label={t('settings.brokerLabel')}>
            <Input value={form.label} onChange={e => setForm(p => ({ ...p, label: e.target.value }))} className="h-10 text-[13px]" />
          </FormRow>
          <PasswordFieldMemo label={t('settings.brokerApiKey')} value={form.api_key} onChange={v => setForm(p => ({ ...p, api_key: v }))} />
          <PasswordFieldMemo label={t('settings.brokerSecret')} value={form.secret_key} onChange={v => setForm(p => ({ ...p, secret_key: v }))} />
          {isOKX && (
            <PasswordFieldMemo label={t('settings.brokerPassphrase')} value={form.passphrase} onChange={v => setForm(p => ({ ...p, passphrase: v }))} />
          )}
          <FormRow label={t('settings.brokerTestnet')}>
            <ToggleInline checked={form.testnet} onChange={v => setForm(p => ({ ...p, testnet: v }))} />
          </FormRow>
          <FormRow label={t('settings.brokerActive')}>
            <ToggleInline checked={form.active} onChange={v => setForm(p => ({ ...p, active: v }))} />
          </FormRow>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="outline" size="sm" onClick={onCancel}>{t('common.cancel')}</Button>
          <Button size="sm" onClick={() => onSave(form)}>{t('common.save')}</Button>
        </div>
      </div>
    </div>
  )
}

function PasswordFieldMemo({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="space-y-1.5">
      <label className="text-[11px] font-medium text-[var(--foreground-muted)]">{label}</label>
      <div className="relative">
        <Input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="••••••••"
          className="h-9 text-[13px] pr-8"
        />
        <button type="button" onClick={() => setVisible(!visible)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] hover:text-[var(--foreground)]">
          {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  )
}

function ToggleInline({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${checked ? 'bg-[var(--primary)]' : 'bg-[var(--surface-3)]'}`}
    >
      <span className={`pointer-events-none block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${checked ? 'translate-x-4' : 'translate-x-0'}`} />
    </button>
  )
}
