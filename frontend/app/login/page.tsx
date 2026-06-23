'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { signIn } from '@/lib/auth-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import Link from 'next/link'

export default function LoginPage() {
  const t = useTranslations()
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await signIn('credentials', {
      username, password, redirect: false,
    })
    setLoading(false)
    if (result?.error) {
      setError(t('auth.invalidCredentials'))
    } else {
      router.push('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <Card className="w-[360px] bg-[var(--surface-2)] border-[var(--border-default)]">
        <CardHeader>
          <CardTitle className="text-center text-lg">{t('auth.login')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="username" className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.username')}</label>
              <Input
                id="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
                className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="password" className="text-[12px] text-[var(--foreground-secondary)]">{t('auth.password')}</label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                className="h-9 bg-[var(--surface-1)] border-[var(--border-default)]"
              />
            </div>
            {error && <p className="text-[12px] text-[var(--destructive)]">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full h-9 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-[var(--background)]">
              {loading ? t('common.loading') : t('auth.loginBtn')}
            </Button>
          </form>
          <p className="mt-4 text-center text-[12px] text-[var(--foreground-muted)]">
            {t('auth.noAccount')}{' '}
            <Link href="/register" className="text-[var(--primary)] hover:underline">
              {t('auth.register')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
