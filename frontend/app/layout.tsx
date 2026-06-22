import type { Metadata } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import { getLocale, getMessages } from 'next-intl/server'
import { SessionProvider } from 'next-auth/react'
import { Toaster } from 'sonner'
import { Fira_Sans, Fira_Code } from 'next/font/google'
import { ThemeProvider } from '@/components/ui/theme-provider'
import { SWRProvider } from '@/lib/swr-config'
import './globals.css'

const firaSans = Fira_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-sans',
})

const firaCode = Fira_Code({
  subsets: ['latin'],
  weight: ['400'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'AStockPursue',
  description: 'Quantitative Trading Terminal',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <html lang={locale} className={`${firaSans.variable} ${firaCode.variable}`}>
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
