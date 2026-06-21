import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { API_BASE } from '@/lib/constants'

export async function bffProxy(req: NextRequest, method: string): Promise<NextResponse> {
  const session = await auth()
  const token = (session as any)?.accessToken
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const path = req.nextUrl.pathname.replace('/api/', '/api/v1/')
  const url = `${API_BASE}${path}${req.nextUrl.search}`
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
    if (method !== 'GET' && method !== 'DELETE') headers['Content-Type'] = 'application/json'
    const body = method === 'GET' || method === 'DELETE' ? undefined : await req.text()
    const res = await fetch(url, { method, headers, body: body || undefined, signal: controller.signal })
    const data = await res.text()
    return new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' },
    })
  } finally {
    clearTimeout(timeout)
  }
}
