'use client'

import { cn } from '@/lib/utils'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Download, Star } from 'lucide-react'

interface StrategyTemplate {
  key: string
  name: string
  name_en: string
  description: string
  category: string
  difficulty: string
  markets: string[]
  default_params: Record<string, any>
  tags: string[]
}

interface StrategyCardProps {
  template: StrategyTemplate
  stats?: {
    sharpe?: number
    max_drawdown?: number
    annual_return?: number
    win_rate?: number
    installs?: number
    rating?: number
  }
  onInstall?: () => void
  onClick?: () => void
}

const CATEGORY_COLORS: Record<string, string> = {
  trend: 'bg-blue-100 text-blue-700',
  mean_reversion: 'bg-green-100 text-green-700',
  momentum: 'bg-orange-100 text-orange-700',
  volatility: 'bg-purple-100 text-purple-700',
  volume: 'bg-indigo-100 text-indigo-700',
  multi_factor: 'bg-pink-100 text-pink-700',
}

const CATEGORY_LABELS: Record<string, string> = {
  trend: '趋势跟踪',
  mean_reversion: '均值回归',
  momentum: '动量',
  volatility: '波动率',
  volume: '成交量',
  multi_factor: '多因子',
}

export function StrategyCard({ template, stats, onInstall, onClick }: StrategyCardProps) {
  const catColor = CATEGORY_COLORS[template.category] || 'bg-gray-100 text-gray-700'
  const catLabel = CATEGORY_LABELS[template.category] || template.category

  return (
    <Card
      className="cursor-pointer hover:border-[var(--primary)] transition-colors"
      onClick={onClick}
    >
      <CardContent className="pt-4 pb-3 space-y-3">
        {/* Header: category + installs/rating */}
        <div className="flex items-center justify-between">
          <Badge className={cn('text-[11px] font-medium', catColor)} variant="secondary">
            {catLabel}
          </Badge>
          {stats && (
            <div className="flex items-center gap-3 text-[11px] text-[var(--foreground-muted)]">
              {stats.rating != null && (
                <span className="flex items-center gap-0.5">
                  <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
                  {stats.rating.toFixed(1)}
                </span>
              )}
              {stats.installs != null && (
                <span className="flex items-center gap-0.5">
                  <Download className="w-3 h-3" />
                  {stats.installs}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Title */}
        <div>
          <h3 className="text-[15px] font-semibold text-[var(--foreground)]">
            {template.name}
          </h3>
          <p className="text-[11px] text-[var(--foreground-muted)] mt-0.5">
            {template.name_en}
          </p>
        </div>

        {/* Description */}
        <p className="text-[12px] text-[var(--foreground-secondary)] leading-relaxed line-clamp-2">
          {template.description}
        </p>

        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-3 gap-2 pt-1">
            <StatItem label="夏普" value={stats.sharpe?.toFixed(2) ?? '—'} />
            <StatItem label="年化" value={stats.annual_return != null ? `${(stats.annual_return * 100).toFixed(1)}%` : '—'} />
            <StatItem label="回撤" value={stats.max_drawdown != null ? `${(stats.max_drawdown * 100).toFixed(1)}%` : '—'} />
          </div>
        )}

        {/* Tags + Install */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex gap-1 flex-wrap">
            {template.tags?.slice(0, 3).map(tag => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--surface-2)] text-[var(--foreground-muted)]">
                {tag}
              </span>
            ))}
          </div>
          {onInstall && (
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-[11px]"
              onClick={(e) => { e.stopPropagation(); onInstall() }}
            >
              <Download className="w-3 h-3 mr-1" />
              安装
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-[var(--foreground-muted)]">{label}</div>
      <div className="text-[13px] font-mono font-semibold text-[var(--foreground)]">{value}</div>
    </div>
  )
}
