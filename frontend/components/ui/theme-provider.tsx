'use client'

import { useEffect } from 'react'

export function ThemeProvider({ children, locale }: { children: React.ReactNode; locale: string }) {
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  return <>{children}</>
}
