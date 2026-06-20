// Generic BFF proxy pattern used by all routes below
// Each file at frontend/app/api/<resource>/route.ts implements:
import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { API_BASE } from '@/lib/constants'

export async function GET(req: NextRequest)   { return proxy(req, 'GET') }
export async function POST(req: NextRequest)  { return proxy(req, 'POST') }
export async function PUT(req: NextRequest)   { return proxy(req, 'PUT') }
export async function DELETE(req: NextRequest){ return proxy(req, 'DELETE') }

async function proxy(req: NextRequest, method: string) {
  const session = await auth()
  const token = (session as any)?.accessToken
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  // /api/backtest → /api/v1/backtest, /api/backtest/run → /api/v1/backtest/run
  const path = req.nextUrl.pathname.replace('/api/', '/api/v1/')
  const url = `${API_BASE}${path}${req.nextUrl.search}`

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (method !== 'GET' && method !== 'DELETE') {
    headers['Content-Type'] = 'application/json'
  }

  const body = method === 'GET' || method === 'DELETE' ? undefined : await req.text()

  const res = await fetch(url, { method, headers, body: body || undefined })
  const data = await res.text()

  return new NextResponse(data, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' },
  })
}
