// frontend/app/agent/page.tsx — AI Agent chat
'use client'

import { useState, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CodeMirror } from '@/components/financial/CodeMirror'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { Plus, MessageSquare, Trash2 } from 'lucide-react'

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

// ——— Message content renderer ———

function hasQuestion(content: string): boolean {
  return content.includes('?') || content.includes('？')
}

function hasBulletPoints(content: string): boolean {
  return content.includes('•') || content.includes('※') || /^[ \t]*[-*]\s/m.test(content)
}

function hasBacktestResults(content: string): boolean {
  return content.includes('夏普') || content.includes('回测')
}

function extractBacktestMetrics(content: string) {
  const metrics: Record<string, string> = {}
  const patterns: Record<string, RegExp> = {
    '夏普比率': /夏普[比率]*[：:]\s*([\d.]+)/,
    '年化收益': /年化[收益]*[率]*[：:]\s*([\d.]+%?)/,
    '最大回撤': /(最大)?回撤[：:]\s*([\d.]+%?)/,
    '胜率': /胜率[：:]\s*([\d.]+%?)/,
    '总交易': /(总)?交易[次数]*[：:]\s*(\d+)/,
  }
  for (const [key, re] of Object.entries(patterns)) {
    const m = content.match(re)
    if (m) {
      metrics[key] = m[1] || m[2]
    }
  }
  return Object.keys(metrics).length > 0 ? metrics : null
}

function extractBulletItems(content: string): string[] {
  const items: string[] = []
  for (const line of content.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('•') || trimmed.startsWith('※') || (/^[-*]\s/.test(trimmed) && trimmed.length > 2)) {
      items.push(trimmed.replace(/^[•※\-\*]\s*/, ''))
    }
  }
  return items
}

function MessageContent({ msg }: { msg: Message }) {
  const content = msg.content

  // Question highlight — add colored left border
  const showQuestionBorder = msg.role === 'assistant' && hasQuestion(content)

  // Strategy params card
  const bulletItems = msg.role === 'assistant' && hasBulletPoints(content) ? extractBulletItems(content) : []

  // Backtest mini card
  const backtestMetrics = msg.role === 'assistant' && hasBacktestResults(content) ? extractBacktestMetrics(content) : null

  return (
    <div
      className={cn(
        showQuestionBorder && 'border-l-2 border-[var(--primary)] pl-3'
      )}
    >
      {/* Main text content */}
      <div className="whitespace-pre-wrap break-words">{content}</div>

      {/* Bullet points info card */}
      {bulletItems.length > 0 && (
        <div className="mt-2 bg-[var(--primary)]/5 border border-[var(--primary)]/15 rounded-[var(--radius-sm)] p-3">
          <div className="text-[11px] font-semibold text-[var(--primary)] mb-1.5">策略参数</div>
          <ul className="space-y-1">
            {bulletItems.map((item, i) => (
              <li key={i} className="text-[12px] text-[var(--foreground-secondary)] flex gap-1.5">
                <span className="text-[var(--primary)] shrink-0 mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Backtest results mini card */}
      {backtestMetrics && (
        <div className="mt-2 bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-sm)] p-3">
          <div className="text-[11px] font-semibold text-[var(--foreground)] mb-2">回测结果摘要</div>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(backtestMetrics).map(([label, value]) => (
              <div key={label} className="text-center bg-[var(--surface-1)] rounded-[4px] py-1.5 px-2">
                <div className="text-[10px] text-[var(--foreground-muted)]">{label}</div>
                <div className="text-[13px] font-mono font-semibold text-[var(--foreground)]">{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ——— Main Agent page ———

export default function AgentPage() {
  const t = useTranslations()
  const [sessionId, setSessionId] = useState<string | null>(null)
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

  // AC2: Fetch conversation threads / sessions
  const {
    data: threadsData,
    isLoading: threadsLoading,
    mutate: mutateThreads,
  } = useSWR('/api/agent/threads')

  // Fetch sessions from /api/v1/agent/sessions
  const { data: sessionsData } = useSWR('/api/v1/agent/sessions')

  const threads: Thread[] = threadsData?.threads || threadsData?.data || threadsData || []
  const sessions: Thread[] = sessionsData?.sessions || sessionsData?.data || sessionsData || []

  // Merge threads and sessions
  const allSessions = [
    ...(Array.isArray(threads) ? threads : []),
    ...(Array.isArray(sessions)
      ? sessions.filter((s: Thread) => !(Array.isArray(threads) && threads.some((t: Thread) => t.id === s.id)))
      : []),
  ]

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

  // Start new chat
  const handleNewChat = () => {
    setSessionId(null)
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: t('agent.welcome'),
      },
    ])
    setInput('')
  }

  // Load session messages
  const handleSelectThread = async (threadId: string) => {
    try {
      const res = await fetch(`/api/v1/agent/sessions/${threadId}`)
      const data = await res.json()
      const sessionMessages = data?.messages || data?.data?.messages || []
      if (sessionMessages.length > 0) {
        setSessionId(threadId)
        setMessages(sessionMessages.map((m: { role: string; content: string }, i: number) => ({
          id: `session-${threadId}-${i}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
        })))
        setSidebarOpen(false)
      }
    } catch {
      toast.error('加载会话失败')
    }
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
      const res = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
          messages: [
            ...messages.map((m) => ({ role: m.role, content: m.content })),
            { role: 'user', content },
          ],
          skills: activeSkills,
        }),
      })

      const data = await res.json()

      // Save session ID from response
      if (data.session_id && !sessionId) {
        setSessionId(data.session_id)
        mutateThreads()
      }

      const reply = data?.data?.content || data?.reply || data?.content || 'No response received.'

      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: reply,
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch {
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

  return (
    <SidebarLayout>
      <div className="flex gap-3" style={{ height: 'calc(100vh - var(--header-height) - var(--page-padding) * 2)' }}>
        {/* AC2: Conversation threads sidebar */}
        <div
          className={cn(
            'shrink-0 bg-[var(--surface-2)] border border-[var(--border-default)] rounded-[var(--radius-sm)] overflow-hidden transition-all flex flex-col',
            sidebarOpen ? 'w-[220px]' : 'w-0 border-0'
          )}
        >
          <div className="p-3 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-[12px] font-semibold text-[var(--foreground)]">
                {t('agent.threads')}
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={handleNewChat}
                title="新建对话"
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            {threadsLoading ? (
              <div className="text-[12px] text-[var(--foreground-muted)]">{t('common.loading')}</div>
            ) : allSessions.length > 0 ? (
              <div className="space-y-1">
                {allSessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => handleSelectThread(session.id)}
                    className={cn(
                      'w-full text-left text-[12px] rounded-[4px] px-2 py-1.5 truncate transition-colors flex items-center gap-1.5',
                      session.id === sessionId
                        ? 'bg-[var(--primary)]/10 text-[var(--primary)]'
                        : 'text-[var(--foreground-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--surface-3)]'
                    )}
                  >
                    <MessageSquare className="w-3 h-3 shrink-0 opacity-60" />
                    {session.title || session.id}
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
            <div className="flex items-center gap-2">
              {sessionId && (
                <span className="text-[11px] text-[var(--foreground-muted)] truncate max-w-[200px]">
                  #{sessionId}
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-[11px] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                onClick={handleNewChat}
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                新对话
              </Button>
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
                    <MessageContent msg={msg} />
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
