// frontend/app/settings/page.tsx — Settings form
'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { Card } from '@/components/ui/card'

interface Settings {
  language?: string
  theme?: string
  default_market?: string
  notifications_enabled?: boolean
}

export default function SettingsPage() {
  const t = useTranslations()
  const [settings, setSettings] = useState<Settings>({
    language: 'en',
    theme: 'compact',
    default_market: 'cn',
    notifications_enabled: true,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/settings')
      .then((res) => res.json())
      .then((json) => {
        const data = json?.data || json || {}
        setSettings({
          language: data.language || 'en',
          theme: data.theme || 'compact',
          default_market: data.default_market || 'cn',
          notifications_enabled: data.notifications_enabled !== false,
        })
      })
      .catch(() => setError('Failed to load settings'))
      .finally(() => setIsLoading(false))
  }, [])

  const handleSave = async () => {
    setIsSaving(true)
    setError(null)
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      if (res.ok) {
        toast.success('Settings saved')
      } else {
        toast.error('Failed to save settings')
      }
    } catch {
      toast.error('Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-3 max-w-2xl">
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.settings')}</h1>

        {/* Loading state */}
        {isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--foreground-muted)] text-center py-12">{t('common.loading')}</div>
          </Card>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-0 overflow-hidden">
            <div className="text-[13px] text-[var(--down)] text-center py-12">
              {error}
              <button
                className="ml-2 underline text-[var(--foreground-secondary)]"
                onClick={() => window.location.reload()}
              >
                {t('common.retry')}
              </button>
            </div>
          </Card>
        )}

        {/* Settings form */}
        {!isLoading && !error && (
          <Card className="bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)]">
            <div className="space-y-4">
              {/* Language */}
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                  Language
                </label>
                <select
                  value={settings.language}
                  onChange={(e) => setSettings({ ...settings, language: e.target.value })}
                  className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 focus:outline-none focus:border-[var(--primary)]"
                >
                  <option value="en">English</option>
                  <option value="zh">中文</option>
                </select>
              </div>

              {/* Theme */}
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                  Theme Preset
                </label>
                <select
                  value={settings.theme}
                  onChange={(e) => setSettings({ ...settings, theme: e.target.value })}
                  className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 focus:outline-none focus:border-[var(--primary)]"
                >
                  <option value="compact">Compact</option>
                  <option value="standard">Standard</option>
                </select>
              </div>

              {/* Default Market */}
              <div>
                <label className="block text-[13px] font-medium text-[var(--foreground)] mb-1.5">
                  Default Market
                </label>
                <select
                  value={settings.default_market}
                  onChange={(e) => setSettings({ ...settings, default_market: e.target.value })}
                  className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] text-[var(--foreground)] text-[13px] rounded-[var(--radius-sm)] px-3 py-1.5 focus:outline-none focus:border-[var(--primary)]"
                >
                  <option value="cn">China A-Share</option>
                  <option value="hk">Hong Kong</option>
                  <option value="us">US Market</option>
                  <option value="crypto">Crypto</option>
                </select>
              </div>

              {/* Notifications */}
              <div className="flex items-center justify-between">
                <label className="text-[13px] font-medium text-[var(--foreground)]">
                  Notifications
                </label>
                <button
                  onClick={() => setSettings({ ...settings, notifications_enabled: !settings.notifications_enabled })}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    settings.notifications_enabled ? 'bg-[var(--primary)]' : 'bg-[var(--border-default)]'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                      settings.notifications_enabled ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>

              {/* Save button */}
              <div className="pt-2">
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? t('common.loading') : t('common.save')}
                </button>
              </div>
            </div>
          </Card>
        )}
      </div>
    </SidebarLayout>
  )
}
