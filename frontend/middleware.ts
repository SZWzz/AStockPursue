// frontend/middleware.ts
import NextAuth from 'next-auth'
import { authConfig } from '@/lib/auth.config'

export default NextAuth(authConfig).auth

export const config = {
  matcher: ['/((?!api/auth|login|register|_next/static|_next/image|favicon.ico).*)'],
}

// ── BFF error aggregation ──
// Translates HTTP error status codes to user-friendly Chinese messages.
export const ERROR_MAP: Record<number, string> = {
  503: 'Python 研究层离线，部分功能不可用',
  500: '服务内部错误，请稍后重试',
  502: '后端服务不可用',
}

export function translateError(status: number): string {
  return ERROR_MAP[status] || `请求失败 (HTTP ${status})`
}
