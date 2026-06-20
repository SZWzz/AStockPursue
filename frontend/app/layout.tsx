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
    <html lang={locale} className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Fira+Sans:wght@400;600;700&display=swap" rel="stylesheet" />
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
                    background: 'var(--surface-3)',
                    color: 'var(--foreground)',
                    border: '1px solid var(--border-default)',
                    fontSize: '13px',
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
