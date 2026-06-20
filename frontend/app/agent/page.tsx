// frontend/app/agent/page.tsx — AI Agent chat
'use client'

import { useState, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CodeMirror } from '@/components/financial/CodeMirror'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string | number
}

export default function AgentPage() {
  const t = useTranslations()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hello! I am your AI trading assistant. I can help with factor analysis, strategy research, market insights, and more. How can I assist you today?',
    },
  ])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const content = input.trim()
    if (!content || isSending) return

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsSending(true)

    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            ...messages.map((m) => ({ role: m.role, content: m.content })),
            { role: 'user', content },
          ],
        }),
      })

      const data = await res.json()
      const reply = data?.data?.content || data?.reply || data?.content || 'No response received.'

      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: reply,
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (e) {
      console.error('Failed to send message', e)
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, an error occurred. Please try again.',
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <SidebarLayout>
      <div className="flex flex-col" style={{ height: 'calc(100vh - var(--header-height) - var(--page-padding) * 2)' }}>
        {/* Header */}
        <h1 className="text-[20px] font-semibold text-[var(--foreground)] mb-3 shrink-0">{t('nav.agent')}</h1>

        {/* Message history */}
        <Card className="flex-1 bg-[var(--surface-2)] border-[var(--border-default)] p-[var(--card-padding)] overflow-hidden mb-3 min-h-0">
          <div className="h-full overflow-y-auto space-y-3 pr-1">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  'flex',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                <div
                  className={cn(
                    'max-w-[80%] rounded-[var(--radius-md)] px-3 py-2 text-[13px] leading-relaxed',
                    msg.role === 'user'
                      ? 'bg-[var(--primary)]/15 text-[var(--foreground)] border border-[var(--primary)]/20'
                      : 'bg-[var(--surface-1)] text-[var(--foreground-secondary)] border border-[var(--border-subtle)]'
                  )}
                >
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {isSending && (
              <div className="flex justify-start">
                <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-[var(--radius-md)] px-3 py-2 text-[13px] text-[var(--foreground-muted)]">
                  <span className="inline-flex gap-1">
                    <span className="animate-pulse">.</span>
                    <span className="animate-pulse" style={{ animationDelay: '0.2s' }}>.</span>
                    <span className="animate-pulse" style={{ animationDelay: '0.4s' }}>.</span>
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </Card>

        {/* Input area */}
        <div className="shrink-0 flex items-end gap-2">
          <div className="flex-1 border border-[var(--border-default)] rounded-[var(--radius-sm)] overflow-hidden" style={{ height: 120 }}>
            <CodeMirror
              value={input}
              readOnly={false}
              language="python"
              onChange={(value) => setInput(value)}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={isSending || !input.trim()}
            className="bg-[var(--primary)] text-white text-[13px] font-medium px-4 py-1.5 rounded-[var(--radius-sm)] hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed shrink-0 mb-1"
          >
            {isSending ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </SidebarLayout>
  )
}
