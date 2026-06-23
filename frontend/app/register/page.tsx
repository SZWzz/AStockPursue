'use client'

import { useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import Link from 'next/link'
import { API_BASE } from '@/lib/constants'

function getPasswordStrength(pw: string): { level: 'none' | 'weak' | 'medium' | 'strong'; score: number; checks: { length: boolean; upper: boolean; lower: boolean; digit: boolean; special: boolean } } {
  if (!pw) return { level: 'none', score: 0, checks: { length: false, upper: false, lower: false, digit: false, special: false } }
  const checks = {
    length: pw.length >= 8,
    upper: /[A-Z]/.test(pw),
    lower: /[a-z]/.test(pw),
    digit: /\d/.test(pw),
    special: /[^A-Za-z0-9]/.test(pw),
  }
  const score = Object.values(checks).filter(Boolean).length
  if (score <= 1) return { level: 'weak', score, checks }
  if (score <= 2) return { level: 'weak', score, checks }
  if (score <= 3) return { level: 'medium', score, checks }
  return { level: 'strong', score: 4, checks }
}

export default function RegisterPage() {
  const t = useTranslations()
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const strength = useMemo(() => getPasswordStrength(password), [password])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 8 || !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
      setError(t('auth.minPasswordLength'))
      return
    }
    if (password !== confirm) {
      setError(t('auth.passwordMismatch'))
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        const data = await res.json()
        setError(data.error || t('auth.registrationFailed'))
        return
      }
      router.push('/login')
    } catch {
      setError(t('auth.networkError'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <Card className="w-[360px] bg-[var(--surface-2)] border-[var(--border-default)]">
        <CardHeader>
          <CardTitle className="text-center text-lg">{t('auth.register')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="username" className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.username')}</label>
              <Input id="username" value={username} onChange={e => setUsername(e.target.value)} required className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            <div className="space-y-1">
              <label htmlFor="password" className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.password')}</label>
              <Input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} required className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]" />
              {/* RE2: Password strength indicator */}
              {password && (
                <div className="mt-1 space-y-1">
                  {/* 5-segment strength bar */}
                  <div className="flex gap-0.5">
                    {(['length', 'upper', 'lower', 'digit', 'special'] as const).map((key) => {
                      const checkColor = strength.checks[key]
                        ? strength.level === 'strong' ? 'var(--up)' : strength.level === 'medium' ? '#F5A623' : strength.level === 'weak' ? 'var(--down)' : 'var(--border-subtle)'
                        : 'var(--border-subtle)'
                      return (
                        <div
                          key={key}
                          className="h-1.5 flex-1 rounded-full transition-colors duration-300"
                          style={{ backgroundColor: checkColor }}
                        />
                      )
                    })}
                  </div>
                  {/* Criterion checklist */}
                  <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                    {([
                      { key: 'length' as const, label: '≥ 8 chars' },
                      { key: 'upper' as const, label: 'A-Z' },
                      { key: 'lower' as const, label: 'a-z' },
                      { key: 'digit' as const, label: '0-9' },
                      { key: 'special' as const, label: '#?!@' },
                    ]).map(({ key, label }) => (
                      <div key={key} className="flex items-center gap-1">
                        <span
                          className="text-[10px] leading-none"
                          style={{ color: strength.checks[key] ? 'var(--up)' : 'var(--foreground-muted)' }}
                        >
                          {strength.checks[key] ? '✔' : '○'}
                        </span>
                        <span className="text-[10px] text-[var(--foreground-muted)]">{label}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-[var(--foreground-muted)]">
                      {t('auth.passwordStrength')}:{' '}
                      <span className="font-medium" style={{
                        color: strength.level === 'strong' ? 'var(--up)' : strength.level === 'medium' ? '#F5A623' : 'var(--down)',
                      }}>
                        {t(`auth.${strength.level}`)}
                      </span>
                    </span>
                  </div>
                </div>
              )}
              <p className="text-[10px] text-[var(--foreground-muted)] mt-0.5">{t('auth.minPasswordLength')}</p>
            </div>
            <div className="space-y-1">
              <label htmlFor="confirmPassword" className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.confirmPassword')}</label>
              <Input id="confirmPassword" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]" />
            </div>
            {error && <p className="text-[12px] text-[var(--destructive)]">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full h-9 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-[var(--background)]">
              {loading ? t('common.loading') : t('auth.registerBtn')}
            </Button>
          </form>
          <p className="mt-4 text-center text-[12px] text-[var(--foreground-muted)]">
            {t('auth.hasAccount')}{' '}
            <Link href="/login" className="text-[var(--primary)] hover:underline">
              {t('auth.login')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
