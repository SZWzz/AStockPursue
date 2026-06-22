import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { API_BASE } from '@/lib/constants'

const MAX_BODY_SIZE = 10 * 1024 * 1024 // 10MB
const RATE_LIMIT_MAX = 60
const RATE_LIMIT_WINDOW_MS = 60_000

const rateLimitMap = new Map<string, { count: number; resetTime: number }>()

function checkRateLimit(ip: string): boolean {
  const now = Date.now()
  const entry = rateLimitMap.get(ip)
  if (!entry || now > entry.resetTime) {
    rateLimitMap.set(ip, { count: 1, resetTime: now + RATE_LIMIT_WINDOW_MS })
    return true
  }
  if (entry.count >= RATE_LIMIT_MAX) return false
  entry.count++
  return true
}

export async function bffProxy(req: NextRequest, method: string): Promise<NextResponse> {
  const ip = req.headers.get('x-forwarded-for') || 'unknown'
  if (!checkRateLimit(ip)) {
    return NextResponse.json(
      { error: 'Too Many Requests', code: 'RATE_LIMIT_EXCEEDED' },
      { status: 429 }
    )
  }

  const session = await auth()
  const token = session?.accessToken
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const path = req.nextUrl.pathname.replace('/api/', '/api/v1/')
  const url = `${API_BASE}${path}${req.nextUrl.search}`
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
    if (method !== 'GET' && method !== 'DELETE') headers['Content-Type'] = 'application/json'
    const body = method === 'GET' || method === 'DELETE' ? undefined : await req.text()
    if (body && body.length > MAX_BODY_SIZE) {
      return NextResponse.json(
        { error: 'Request body too large', code: 'BODY_TOO_LARGE' },
        { status: 413 }
      )
    }
    const res = await fetch(url, { method, headers, body: body || undefined, signal: controller.signal })

    let data: unknown
    try {
      data = await res.json()
    } catch {
      data = await res.text()
    }

    return NextResponse.json(data, { status: res.status })
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      return NextResponse.json(
        { error: 'Backend request timed out', code: 'BACKEND_TIMEOUT' },
        { status: 504 }
      )
    }
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'BACKEND_UNREACHABLE' },
      { status: 502 }
    )
  } finally {
    clearTimeout(timeout)
  }
}
