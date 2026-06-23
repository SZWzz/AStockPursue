'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { toast } from 'sonner'
import { Trophy, Send } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Ranking {
  rank: number
  strategy_name: string
  sharpe_ratio: number
  annual_return: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  user_id: number
}

const RANK_COLORS: Record<number, { bg: string; text: string; icon: string }> = {
  1: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: '🥇' },
  2: { bg: 'bg-slate-100', text: 'text-slate-600', icon: '🥈' },
  3: { bg: 'bg-amber-50', text: 'text-amber-600', icon: '🥉' },
}

const MAX_SUBMISSIONS = 5

const fetcher = (url: string) => fetch(url).then(r => r.json())

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatNum(value: number, decimals = 2) {
  return value.toFixed(decimals)
}

function SharpeBadge({ value }: { value: number }) {
  const color = value >= 1.5 ? 'text-emerald-600' : value >= 1.0 ? 'text-amber-600' : 'text-red-600'
  return <span className={cn('font-mono', color)}>{formatNum(value)}</span>
}

export function ArenaContent() {
  const [activeTab, setActiveTab] = useState('rankings')
  const [strategyName, setStrategyName] = useState('')
  const [strategyCode, setStrategyCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submissionCount, setSubmissionCount] = useState(0)

  const { data, error, isLoading, mutate } = useSWR('/api/v1/arena/rankings', fetcher, {
    refreshInterval: 30000,
  })

  const rankings: Ranking[] = data?.rankings || data?.data || data || []

  const handleSubmit = async () => {
    if (!strategyName.trim() || !strategyCode.trim()) {
      toast.error('请填写策略名称和代码')
      return
    }
    if (submissionCount >= MAX_SUBMISSIONS) {
      toast.error('本周提交次数已用完')
      return
    }

    setSubmitting(true)
    try {
      const res = await fetch('/api/v1/arena/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: strategyName.trim(),
          code: strategyCode.trim(),
        }),
      })
      if (!res.ok) throw new Error('提交失败')
      toast.success('策略已提交，等待评估')
      setStrategyName('')
      setStrategyCode('')
      setSubmissionCount(prev => prev + 1)
      mutate()
    } catch {
      toast.error('提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <TabsList className="w-full justify-start border-b border-[var(--border)] rounded-none bg-transparent p-0 h-auto gap-0 overflow-x-auto mb-4">
        <TabsTrigger
          value="rankings"
          className="text-[13px] px-4 py-2.5 border-b-2 border-transparent data-[state=active]:border-[var(--primary)] data-[state=active]:text-[var(--primary)] data-[state=active]:shadow-none rounded-none bg-transparent hover:text-[var(--foreground)] shrink-0"
        >
          <Trophy className="w-4 h-4 mr-1.5 inline" />
          排行榜
        </TabsTrigger>
        <TabsTrigger
          value="submit"
          className="text-[13px] px-4 py-2.5 border-b-2 border-transparent data-[state=active]:border-[var(--primary)] data-[state=active]:text-[var(--primary)] data-[state=active]:shadow-none rounded-none bg-transparent hover:text-[var(--foreground)] shrink-0"
        >
          <Send className="w-4 h-4 mr-1.5 inline" />
          提交策略
        </TabsTrigger>
      </TabsList>

      {/* Leaderboard Tab */}
      <TabsContent value="rankings" className="mt-0">
        <Card className="border-[var(--border-default)]">
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-8 text-center text-[13px] text-[var(--foreground-muted)]">
                加载中...
              </div>
            ) : error ? (
              <div className="p-8 text-center text-[13px] text-[var(--foreground-muted)]">
                加载失败，请刷新重试
              </div>
            ) : rankings.length === 0 ? (
              <div className="p-8 text-center text-[13px] text-[var(--foreground-muted)]">
                暂无排名数据
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[80px]">排名</TableHead>
                    <TableHead>策略名称</TableHead>
                    <TableHead className="text-right">夏普</TableHead>
                    <TableHead className="text-right">年化</TableHead>
                    <TableHead className="text-right">回撤</TableHead>
                    <TableHead className="text-right">胜率</TableHead>
                    <TableHead className="text-right">交易次数</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rankings.map((item) => {
                    const colors = RANK_COLORS[item.rank]
                    return (
                      <TableRow
                        key={item.rank}
                        className={cn(
                          item.rank <= 3 && colors?.bg,
                          item.rank <= 3 && 'font-medium'
                        )}
                      >
                        <TableCell>
                          <span className={cn('text-[15px]', item.rank <= 3 && colors?.text)}>
                            {colors?.icon ? `${colors.icon} ` : ''}
                            {item.rank}
                          </span>
                        </TableCell>
                        <TableCell className={cn(item.rank <= 3 && colors?.text)}>
                          {item.strategy_name}
                        </TableCell>
                        <TableCell className="text-right">
                          <SharpeBadge value={item.sharpe_ratio} />
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatPercent(item.annual_return)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-red-600">
                          {formatPercent(Math.abs(item.max_drawdown))}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatPercent(item.win_rate)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {item.total_trades}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      {/* Submit Tab */}
      <TabsContent value="submit" className="mt-0">
        <Card className="border-[var(--border-default)]">
          <CardContent className="pt-6 pb-4 space-y-4">
            <div>
              <label className="text-[13px] font-medium text-[var(--foreground)] mb-1.5 block">
                策略名称
              </label>
              <Input
                value={strategyName}
                onChange={e => setStrategyName(e.target.value)}
                placeholder="输入策略名称，如：双均线交叉策略"
                className="text-[13px]"
              />
            </div>
            <div>
              <label className="text-[13px] font-medium text-[var(--foreground)] mb-1.5 block">
                策略代码
              </label>
              <Textarea
                value={strategyCode}
                onChange={e => setStrategyCode(e.target.value)}
                placeholder="在此粘贴您的策略代码..."
                className="min-h-[240px] text-[13px] font-mono"
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-[11px]">
                  本周剩余 {MAX_SUBMISSIONS - submissionCount} 次
                </Badge>
                {submissionCount > 0 && (
                  <span className="text-[11px] text-[var(--foreground-muted)]">
                    已提交 {submissionCount} 次
                  </span>
                )}
              </div>
              <Button
                onClick={handleSubmit}
                disabled={submitting || submissionCount >= MAX_SUBMISSIONS}
                className="text-[13px]"
              >
                <Send className="w-4 h-4 mr-1.5" />
                {submitting ? '提交中...' : '提交策略'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  )
}
