// frontend/app/page.tsx
'use client'

import { useTranslations } from 'next-intl'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { StatCallout } from '@/components/financial/StatCallout'
import { KpiCard } from '@/components/financial/KpiCard'
import { PositionTable } from '@/components/financial/PositionTable'
import { EquityChart } from '@/components/financial/EquityChart'
import { usePositions, useSystemStatus } from '@/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { IndexTickerBar } from '@/components/dashboard/IndexTickerBar'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export default function DashboardPage() {
  const t = useTranslations()
  useWebSocket()
  const { data: posData } = usePositions()
  const { data: sysData } = useSystemStatus()
  const { data: portfolio } = useSWR('/api/portfolio', fetcher)
  const { data: northbound } = useSWR('/api/research/northbound?symbol=SH000001', fetcher)
  const { data: geopolitics } = useSWR('/api/research/geopolitics?symbol=SH000001', fetcher)
  const { data: newsData } = useSWR('/api/research/news?symbol=600519', fetcher)

  if (!portfolio && !posData) {
    return (
      <SidebarLayout>
        <EmptyState
          title={t('common.noData')}
          description={t('dashboard.emptyHint') || '还没有记录，连接后端服务以获取数据'}
        />
      </SidebarLayout>
    )
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('nav.dashboard')}
        </h1>

        <IndexTickerBar />

        {/* Hero KPI row — StatCallout for the main equity number */}
        <div className="grid grid-cols-4 gap-[var(--grid-gap)]">
          <StatCallout
            label={t('portfolio.totalEquity')}
            value={portfolio?.total_value ? '$' + Number(portfolio.total_value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
            change={portfolio?.total_value && portfolio?.cash ? ((portfolio.total_value - portfolio.cash) / portfolio.cash * 100).toFixed(2) + '%' : '--'}
            direction={(portfolio?.total_value ?? 0) >= (portfolio?.cash ?? 0) ? 'up' : 'down'}
          />
          <KpiCard
            label={t('portfolio.pnl')}
            value={portfolio?.total_value && portfolio?.cash ? '$' + (portfolio.total_value - portfolio.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
            direction={((portfolio?.total_value ?? 0) - (portfolio?.cash ?? 0)) >= 0 ? 'up' : 'down'}
          />
          <KpiCard
            label={t('portfolio.available')}
            value={portfolio?.cash ? '$' + Number(portfolio.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
          />
          <KpiCard
            label={t('portfolio.margin')}
            value={portfolio?.total_value && portfolio?.cash ? '$' + (portfolio.total_value - portfolio.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
            change={portfolio?.total_value && portfolio?.cash ? ((portfolio.total_value - portfolio.cash) / portfolio.total_value * 100).toFixed(1) + '%' : '--'}
            direction="neutral"
          />
        </div>

        {/* Research Overview + News Brief */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8 space-y-[var(--grid-gap)]">
            <h2 className="text-[18px] font-semibold text-[var(--foreground)]">{t('dashboard.researchOverview')}</h2>
            <div className="grid grid-cols-2 gap-[var(--grid-gap)]">
              {/* Northbound net inflow card */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('dashboard.northboundNetInflow')}</CardTitle>
                </CardHeader>
                <CardContent>
                  {northbound && !northbound.error ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-3 gap-2">
                        <div className="text-center">
                          <div className="text-[10px] text-[var(--muted-foreground)]">{t('dashboard.daily')}</div>
                          <div className={cn('text-lg font-mono font-semibold', northbound.net_inflow_daily >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                            {northbound.net_inflow_daily != null ? (Number(northbound.net_inflow_daily) / 1e8).toFixed(2) + ' 亿' : '--'}
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-[10px] text-[var(--muted-foreground)]">{t('dashboard.weekly')}</div>
                          <div className={cn('text-lg font-mono font-semibold', northbound.net_inflow_weekly >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                            {northbound.net_inflow_weekly != null ? (Number(northbound.net_inflow_weekly) / 1e8).toFixed(2) + ' 亿' : '--'}
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-[10px] text-[var(--muted-foreground)]">{t('dashboard.monthly')}</div>
                          <div className={cn('text-lg font-mono font-semibold', northbound.net_inflow_monthly >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                            {northbound.net_inflow_monthly != null ? (Number(northbound.net_inflow_monthly) / 1e8).toFixed(2) + ' 亿' : '--'}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--muted-foreground)]">--</p>
                  )}
                </CardContent>
              </Card>

              {/* Geopolitics risk summary card */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('dashboard.geopoliticsRisk')}</CardTitle>
                </CardHeader>
                <CardContent>
                  {geopolitics?.topics && geopolitics.topics.length > 0 ? (
                    <div className="space-y-2">
                      {geopolitics.topics.slice(0, 5).map((topic: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between text-xs">
                          <span className="truncate flex-1 min-w-0 pr-2">{topic.name || topic.topic}</span>
                          <Badge
                            variant={
                              (topic.risk_level || '').toLowerCase() === 'high' ? 'destructive' :
                              (topic.risk_level || '').toLowerCase() === 'medium' ? 'warning' :
                              'success'
                            }
                            className="shrink-0 text-[10px] h-5"
                          >
                            {topic.risk_level || 'medium'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--muted-foreground)]">--</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="col-span-4">
            <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-[var(--grid-gap)]">{t('dashboard.newsBrief')}</h2>
            <Card>
              <CardContent>
                {newsData?.articles && newsData.articles.length > 0 ? (
                  <div className="divide-y divide-[var(--border-subtle)]">
                    {newsData.articles.slice(0, 5).map((article: any, idx: number) => (
                      <div key={idx} className="py-2 first:pt-0 last:pb-0">
                        <div className="flex items-start gap-2">
                          <div className={cn(
                            'w-2 h-2 rounded-full shrink-0 mt-1.5',
                            (article.sentiment ?? 0) > 0.3 ? 'bg-[var(--up)]' :
                            (article.sentiment ?? 0) < -0.3 ? 'bg-[var(--down)]' :
                            'bg-[#F4B000]'
                          )} />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs leading-snug line-clamp-2">
                              {article.url ? (
                                <a href={article.url} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--primary)] transition-colors">
                                  {article.title}
                                </a>
                              ) : (
                                article.title
                              )}
                            </p>
                            {article.published_at && (
                              <span className="text-[10px] text-[var(--muted-foreground)] mt-0.5 inline-block">
                                {new Date(article.published_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--muted-foreground)] py-2">{t('dashboard.noNews')}</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Equity Chart + Positions */}
        <div className="grid grid-cols-12 gap-[var(--grid-gap)]">
          <div className="col-span-8">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('backtest.equityCurve')}</h2>
              <EquityChart data={[
                { time: '9:30', equity: 100000 },
                { time: '10:00', equity: 100500 },
                { time: '10:30', equity: 102340 }
              ]} />
            </div>
          </div>
          <div className="col-span-4">
            <div className="bg-white border border-[var(--border)] rounded-[6px] p-[var(--card-padding)]">
              <h2 className="text-[18px] font-semibold text-[var(--foreground)] mb-4">{t('nav.positions')}</h2>
              <PositionTable />
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  )
}
