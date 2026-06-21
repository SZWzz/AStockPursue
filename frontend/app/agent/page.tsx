// frontend/app/agent/page.tsx — AI Agent chat
'use client'

import { useState, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
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

interface Thread {
  id: string
  title: string
  updated_at?: string
}


const AVAILABLE_SKILLS = [
  'factor_analysis',
  'strategy_backtest',
  'market_insight',
  'risk_assessment',
  'portfolio_optimization',
]

export default function AgentPage() {
  const t = useTranslations()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: t('agent.welcome'),
    },
  ])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [activeSkills, setActiveSkills] = useState<string[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // AC2: Fetch conversation threads
  const {
    data: threadsData,
    isLoading: threadsLoading,
  } = useSWR('/api/agent/threads')

  const threads: Thread[] = threadsData?.threads || threadsData?.data || threadsData || []

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // AC3: Toggle skill selection
  const toggleSkill = (skill: string) => {
    setActiveSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    )
  }

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
          skills: activeSkills,
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
        content: String(t('common.error')),
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

  const handleSelectThread = (_threadId: string) => {
    // Placeholder: in a full implementation, load thread messages
    setSidebarOpen(false)
  }

  return (
    <SidebarLayout>
      <div className="flex gap-3" style={{ height: 'calc(100vh - var(--header-height) - var(--page-padding) * 2)' }}>
        {/* AC2: Conversation threads sidebar */}
        <div
          className={cn(
            'shrink-0 bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-sm)] overflow-hidden transition-all',
            sidebarOpen ? 'w-[220px]' : 'w-0 border-0'
          )}
        >
          <div className="p-3">
            <h3 className="text-[12px] font-semibold text-[var(--foreground)] mb-2">
              {t('agent.threads')}
            </h3>
            {threadsLoading ? (
              <div className="text-[12px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
            ) : threads.length > 0 ? (
              <div className="space-y-1">
                {threads.map((thread) => (
                  <button
                    key={thread.id}
                    onClick={() => handleSelectThread(thread.id)}
                    className="w-full text-left text-[12px] text-[var(--foreground-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--surface-3)] rounded-[4px] px-2 py-1 truncate transition-colors"
                  >
                    {thread.title || thread.id}
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-[12px] text-[var(--foreground-muted)]">
                {t('common.noData')}
              </div>
            )}
          </div>
        </div>

        {/* Main chat area */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center justify-between mb-3 shrink-0">
            <div className="flex items-center gap-2">
              <h1 className="text-[20px] font-semibold text-[var(--foreground)]">{t('nav.agent')}</h1>
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-[11px] text-[var(--foreground-muted)] hover:text-[var(--foreground)] px-2 py-0.5 rounded-[4px] hover:bg-[var(--surface-3)] transition-colors"
              >
                {sidebarOpen ? '✕' : t('agent.threads')}
              </button>
            </div>
          </div>

          {/* AC3: Skill selector chips */}
          <div className="flex items-center gap-1.5 mb-2 shrink-0 flex-wrap">
            <span className="text-[11px] text-[var(--foreground-muted)] mr-1">
              {t('agent.skills')}:
            </span>
            {AVAILABLE_SKILLS.map((skill) => (
              <button
                key={skill}
                onClick={() => toggleSkill(skill)}
                className={cn(
                  'text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] border transition-colors',
                  activeSkills.includes(skill)
                    ? 'bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)]'
                    : 'border-[var(--border-default)] text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]'
                )}
              >
                {skill.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

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

              {/* AC1: Typing indicator with animated dots */}
              {isSending && (
                <div className="flex justify-start">
                  <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-[var(--radius-md)] px-4 py-2">
                    <span className="inline-flex gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--foreground-muted)] animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--foreground-muted)] animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--foreground-muted)] animate-bounce" style={{ animationDelay: '300ms' }} />
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
              onKeyDown={handleKeyDown}
            >
              {isSending ? '...' : t('common.send')}
            </button>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
