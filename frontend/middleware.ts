// frontend/middleware.ts
import NextAuth from 'next-auth'
import { authConfig } from '@/lib/auth.config'

export { ERROR_MAP, translateError } from '@/lib/errors'

export default NextAuth(authConfig).auth

export const config = {
  matcher: ['/((?!api/auth|login|register|_next/static|_next/image|favicon.ico).*)'],
}
