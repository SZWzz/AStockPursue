// frontend/lib/auth-client.ts
// Stub for auth client — will be replaced with proper auth implementation

/**
 * Sign out the current user.
 * Placeholder: clears client-side state and redirects to login.
 */
export async function signOut(): Promise<void> {
  // TODO: implement proper sign-out — clear tokens, invalidate session
  // For now, redirect to login page
  if (typeof window !== 'undefined') {
    window.location.href = '/login'
  }
}
