// frontend/middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import NextAuth from 'next-auth'
import { authConfig } from '@/lib/auth.config'

export { ERROR_MAP, translateError } from '@/lib/errors'

type AuthMiddlewareFn = (req: NextRequest) => void | Response | Promise<void | Response>

const authMiddleware = NextAuth(authConfig).auth as unknown as AuthMiddlewareFn

// Routes that need auth protection (original matcher)
const authMatcher = /^\/(?!api\/auth|login|register|_next\/static|_next\/image|favicon\.icon).*/

export default async function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname

  let response: NextResponse

  if (authMatcher.test(path)) {
    // Run auth middleware for protected routes
    const authResponse = await authMiddleware(request)
    response = authResponse instanceof NextResponse ? authResponse : NextResponse.next()
  } else {
    response = NextResponse.next()
  }

  // Set security headers on all responses
  response.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('X-Frame-Options', 'DENY')
  response.headers.set(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' http://localhost:* ws://localhost:*; font-src 'self'",
  )

  return response
}

// Run on all routes except static assets
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
