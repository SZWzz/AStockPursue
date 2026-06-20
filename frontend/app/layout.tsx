import type { Metadata } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import { getLocale, getMessages } from 'next-intl/server'
import { SessionProvider } from 'next-auth/react'
import { Toaster } from 'sonner'
import { ThemeProvider } from '@/components/ui/theme-provider'
import './globals.css'

export const metadata: Metadata = {
  title: 'AStockPursue',
  description: 'Quantitative Trading Terminal',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <html lang={locale}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-[var(--background)] text-[var(--foreground)] antialiased">
        <SessionProvider>
          <NextIntlClientProvider messages={messages}>
            <ThemeProvider locale={locale}>
              {children}
              <Toaster
                position="bottom-right"
                toastOptions={{
                  style: {
                    background: '#FFFFFF',
                    color: '#0A0B0D',
                    border: '1px solid #DEE1E6',
                    fontSize: '14px',
                    fontFamily: 'Inter, system-ui, sans-serif',
                  },
                }}
              />
            </ThemeProvider>
          </NextIntlClientProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
