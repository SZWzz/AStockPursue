// frontend/lib/auth.config.ts
import type { NextAuthConfig } from 'next-auth'

export const authConfig: NextAuthConfig = {
  pages: {
    signIn: '/login',
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user
      const isAuthPage = nextUrl.pathname.startsWith('/login') || nextUrl.pathname.startsWith('/register')
      if (isAuthPage) {
        if (isLoggedIn) return Response.redirect(new URL('/', nextUrl))
        return true
      }
      if (!isLoggedIn) return false
      return true
    },
    jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as any).accessToken
      }
      return token
    },
    session({ session, token }) {
      (session as any).accessToken = token.accessToken
      return session
    },
  },
  providers: [], // populated in auth.ts
}
