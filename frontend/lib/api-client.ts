// frontend/lib/api-client.ts
import { API_BASE } from './constants'

export async function apiFetch<T = any>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API ${res.status}: ${body}`)
  }
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}
