// frontend/lib/auth-client.ts
'use client'

import { signIn as nextSignIn, signOut as nextSignOut, useSession } from 'next-auth/react'

export function useAuth() {
  const { data: session, status } = useSession()
  return {
    user: session?.user,
    token: session?.accessToken as string | undefined,
    isAuthenticated: status === 'authenticated',
    isLoading: status === 'loading',
  }
}

export { nextSignIn as signIn, nextSignOut as signOut }
