import type { Metadata } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import { getLocale, getMessages } from 'next-intl/server'
import { SessionProvider } from 'next-auth/react'
import { Toaster } from 'sonner'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { ThemeProvider } from '@/components/ui/theme-provider'
import { SWRProvider } from '@/lib/swr-config'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-sans',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'AStockPursue — AI-Powered Quantitative Trading',
  description: 'AI-driven quantitative research and trading platform. Describe strategies in natural language, auto backtest, one-click live trading.',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <html lang={locale} className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-[var(--background)] text-[var(--foreground)] antialiased">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-[var(--primary)] focus:text-white focus:rounded-md">
          Skip to content
        </a>
        <SessionProvider>
          <SWRProvider>
            <NextIntlClientProvider messages={messages}>
              <ThemeProvider locale={locale}>
                <main id="main-content">
                  {children}
                </main>
                <Toaster
                  position="bottom-right"
                  toastOptions={{
                    style: {
                      background: '#FFFFFF',
                      color: '#0A0B0D',
                      border: '1px solid #DEE1E6',
                      fontSize: '14px',
                      fontFamily: 'var(--font-sans)',
                    },
                  }}
                />
              </ThemeProvider>
            </NextIntlClientProvider>
          </SWRProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
