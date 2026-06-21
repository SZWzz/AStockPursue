'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import useSWR from 'swr'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { KpiCard } from '@/components/financial/KpiCard'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { Search, TrendingUp, TrendingDown, Minus } from 'lucide-react'


// --------------- helpers ---------------

function riskVariant(level: string): 'destructive' | 'warning' | 'success' | 'secondary' {
  const l = level?.toLowerCase() || ''
  if (l === 'high' || l === '高') return 'destructive'
  if (l === 'medium' || l === '中') return 'warning'
  if (l === 'low' || l === '低') return 'success'
  return 'secondary'
}

function sentimentVariant(score: number): 'success' | 'warning' | 'destructive' | 'secondary' {
  if (score > 0.3) return 'success'
  if (score < -0.3) return 'destructive'
  if (score >= -0.3 && score <= 0.3) return 'warning'
  return 'secondary'
}

function sentimentLabel(score: number, t: (key: string) => string): string {
  if (score > 0.3) return '↑ ' + t('research.positive')
  if (score < -0.3) return '↓ ' + t('research.negative')
  return '→ ' + t('research.neutral')
}

function formatNumber(n: number | undefined | null, decimals = 2): string {
  if (n == null) return '--'
  return Number(n).toFixed(decimals)
}

function formatPercent(n: number | undefined | null): string {
  if (n == null) return '--'
  return (Number(n) * 100).toFixed(2) + '%'
}

// --------------- Financials Tab ---------------

function FinancialsTab({ t }: { t: (key: string) => string }) {
  const [symbol, setSymbol] = useState('600519')
  const [query, setQuery] = useState('')
  const { data, error, isLoading } = useSWR(
    query ? `/api/research/financials?symbol=${query}` : null
  )

  // RS3: empty symbol check
  const handleFetch = () => {
    if (!symbol || !symbol.trim()) return
    setQuery(symbol.trim())
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder={t('research.symbolPlaceholder')}
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleFetch()}
          className="max-w-[200px]"
        />
        <Button onClick={handleFetch} disabled={isLoading}>
          <Search className="w-4 h-4 mr-2" />
          {t('research.fetch')}
        </Button>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">{t('common.loading')}</p>}
      {error && <p className="text-sm text-[var(--down)]">{t('common.error')}</p>}
      {data && !data.error && (
        <div className="grid grid-cols-3 gap-[var(--grid-gap)]">
          <KpiCard label={t('research.revenueYoY')} value={formatPercent(data.revenue_yoy)} direction={data.revenue_yoy >= 0 ? 'up' : 'down'} />
          <KpiCard label={t('research.netProfitYoY')} value={formatPercent(data.net_profit_yoy)} direction={data.net_profit_yoy >= 0 ? 'up' : 'down'} />
          <KpiCard label={t('research.roe')} value={formatPercent(data.roe)} direction={data.roe >= 0 ? 'up' : 'down'} />
          <KpiCard label={t('research.grossMargin')} value={formatPercent(data.gross_margin)} />
          <KpiCard label={t('research.debtToAsset')} value={formatPercent(data.debt_to_asset)} />
          <KpiCard label={t('research.currentRatio')} value={formatNumber(data.current_ratio)} />
          <KpiCard label={t('research.eps')} value={formatNumber(data.eps)} />
          <KpiCard label={t('research.pbRatio')} value={formatNumber(data.pb_ratio)} />
          <KpiCard label={t('research.peRatio')} value={formatNumber(data.pe_ratio)} />
        </div>
      )}
      {data?.error && <p className="text-sm text-[var(--muted-foreground)]">{t('research.noFinancials')}</p>}
    </div>
  )
}

// --------------- Geopolitics Tab ---------------

function GeopoliticsTab({ t }: { t: (key: string) => string }) {
  const [symbol, setSymbol] = useState('SH000001')
  const [query, setQuery] = useState('')
  const { data, error, isLoading } = useSWR(
    query ? `/api/research/geopolitics?symbol=${query}` : null
  )

  // RS3: empty symbol check
  const handleFetch = () => {
    if (!symbol || !symbol.trim()) return
    setQuery(symbol.trim())
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder={t('research.indexPlaceholder')}
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleFetch()}
          className="max-w-[200px]"
        />
        <Button onClick={handleFetch} disabled={isLoading}>
          <Search className="w-4 h-4 mr-2" />
          {t('research.fetch')}
        </Button>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">{t('common.loading')}</p>}
      {error && <p className="text-sm text-[var(--down)]">{t('common.error')}</p>}
      {data?.topics && data.topics.length > 0 ? (
        <div className="grid grid-cols-2 gap-[var(--grid-gap)]">
          {data.topics.slice(0, 10).map((topic: any, idx: number) => (
            <Card key={idx} size="sm">
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm truncate">{topic.name || topic.topic}</h3>
                    {topic.description && (
                      <p className="text-xs text-[var(--muted-foreground)] mt-1 line-clamp-2">{topic.description}</p>
                    )}
                  </div>
                  <Badge variant={riskVariant(topic.risk_level)} className="shrink-0 ml-2">
                    {topic.risk_level || t('research.medium')}
                  </Badge>
                </div>
                <div className="flex items-center gap-4 mt-3 text-xs text-[var(--muted-foreground)]">
                  <span>{t('research.tone')}: {formatNumber(topic.tone_score, 2)}</span>
                  <span className={cn(
                    'flex items-center gap-1',
                    (topic.tone_change ?? 0) > 0 ? 'text-[var(--up)]' : (topic.tone_change ?? 0) < 0 ? 'text-[var(--down)]' : ''
                  )}>
                    {t('research.toneChange')}: {(topic.tone_change ?? 0) > 0 ? <TrendingUp className="w-3 h-3" /> : (topic.tone_change ?? 0) < 0 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                    {formatNumber(topic.tone_change, 4)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        data && <p className="text-sm text-[var(--muted-foreground)]">{t('research.noGeopolitics')}</p>
      )}
    </div>
  )
}

// --------------- Northbound Tab ---------------

function NorthboundTab({ t }: { t: (key: string) => string }) {
  const [symbol, setSymbol] = useState('SH000001')
  const [query, setQuery] = useState('')
  const { data, error, isLoading } = useSWR(
    query ? `/api/research/northbound?symbol=${query}` : null
  )

  // RS3: empty symbol check
  const handleFetch = () => {
    if (!symbol || !symbol.trim()) return
    setQuery(symbol.trim())
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder={t('research.indexPlaceholder')}
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleFetch()}
          className="max-w-[200px]"
        />
        <Button onClick={handleFetch} disabled={isLoading}>
          <Search className="w-4 h-4 mr-2" />
          {t('research.fetch')}
        </Button>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">{t('common.loading')}</p>}
      {error && <p className="text-sm text-[var(--down)]">{t('common.error')}</p>}
      {data && !data.error && (
        <>
          <div className="grid grid-cols-3 gap-[var(--grid-gap)]">
            <KpiCard label={t('research.netInflow') + ' (' + t('dashboard.daily') + ')'} value={data.net_inflow_daily != null ? (Number(data.net_inflow_daily) / 1e8).toFixed(2) + ' 亿' : '--'} direction={data.net_inflow_daily >= 0 ? 'up' : 'down'} />
            <KpiCard label={t('research.netInflow') + ' (' + t('dashboard.weekly') + ')'} value={data.net_inflow_weekly != null ? (Number(data.net_inflow_weekly) / 1e8).toFixed(2) + ' 亿' : '--'} direction={data.net_inflow_weekly >= 0 ? 'up' : 'down'} />
            <KpiCard label={t('research.netInflow') + ' (' + t('dashboard.monthly') + ')'} value={data.net_inflow_monthly != null ? (Number(data.net_inflow_monthly) / 1e8).toFixed(2) + ' 亿' : '--'} direction={data.net_inflow_monthly >= 0 ? 'up' : 'down'} />
          </div>

          {data.top10_active_stocks && data.top10_active_stocks.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t('research.top10Active')}</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('portfolio.symbol')}</TableHead>
                      <TableHead>{t('research.netInflow')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.top10_active_stocks.map((s: any, idx: number) => (
                      <TableRow key={idx}>
                        <TableCell className="font-mono">{s.symbol || s.code}</TableCell>
                        <TableCell className={cn('font-mono', (s.net_inflow ?? 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]')}>
                          {s.net_inflow != null ? (Number(s.net_inflow) / 1e8).toFixed(2) + ' 亿' : '--'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {data.sector_distribution && data.sector_distribution.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t('research.sectorDistribution')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {data.sector_distribution.map((sec: any, idx: number) => (
                    <Badge key={idx} variant="secondary" className="text-xs">
                      {sec.sector || sec.name}: {(sec.inflow != null ? (Number(sec.inflow) / 1e8).toFixed(2) + ' 亿' : '--')}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
      {data?.error && <p className="text-sm text-[var(--muted-foreground)]">{t('research.noNorthbound')}</p>}
    </div>
  )
}

// --------------- News Tab ---------------

function NewsTab({ t }: { t: (key: string) => string }) {
  const [symbol, setSymbol] = useState('600519')
  const [query, setQuery] = useState('')
  // RS2: date range filter
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const { data, error, isLoading } = useSWR(
    query ? `/api/research/news?symbol=${query}${startDate ? '&start_date=' + startDate : ''}${endDate ? '&end_date=' + endDate : ''}` : null
  )

  // RS3: empty symbol check
  const handleFetch = () => {
    if (!symbol || !symbol.trim()) return
    setQuery(symbol.trim())
  }

  return (
      <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        <Input
          placeholder={t('research.symbolPlaceholder')}
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleFetch()}
          className="max-w-[200px]"
        />
        {/* RS2: date range inputs */}
        <Input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="max-w-[160px]"
        />
        <Input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="max-w-[160px]"
        />
        <Button onClick={handleFetch} disabled={isLoading}>
          <Search className="w-4 h-4 mr-2" />
          {t('research.fetch')}
        </Button>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">{t('common.loading')}</p>}
      {error && <p className="text-sm text-[var(--down)]">{t('common.error')}</p>}
      {data && !data.error && (
        <>
          {/* Overall sentiment gauge */}
          {data.overall_sentiment != null && (
            <div className="flex items-center gap-3 p-4 rounded-[6px] bg-[var(--surface-1)]">
              <span className="text-sm font-semibold">{t('research.overallSentiment')}:</span>
              <Badge variant={sentimentVariant(data.overall_sentiment)}>
                {sentimentLabel(data.overall_sentiment, t)} ({formatNumber(data.overall_sentiment)})
              </Badge>
            </div>
          )}

          {/* Key topics */}
          {data.key_topics && data.key_topics.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2">{t('research.keyTopics')}</h3>
              <div className="flex flex-wrap gap-1.5">
                {data.key_topics.map((topic: string, idx: number) => (
                  <Badge key={idx} variant="outline" className="text-xs">{topic}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* Article list */}
          {data.articles && data.articles.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>{t('research.articles')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="divide-y divide-[var(--border-subtle)]">
                  {data.articles.map((article: any, idx: number) => (
                    <div key={idx} className="py-3 first:pt-0 last:pb-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium leading-snug">
                            {article.url ? (
                              <a href={article.url} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--primary)] transition-colors">
                                {article.title}
                              </a>
                            ) : (
                              article.title
                            )}
                          </h4>
                          {article.summary && (
                            <p className="text-xs text-[var(--muted-foreground)] mt-1 line-clamp-2">{article.summary}</p>
                          )}
                          {article.published_at && (
                            <span className="text-xs text-[var(--muted-foreground)] mt-1 inline-block">{article.published_at}</span>
                          )}
                        </div>
                        {article.sentiment != null && (
                          <Badge variant={sentimentVariant(article.sentiment)} className="shrink-0">
                            {formatNumber(article.sentiment)}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">{t('research.noNews')}</p>
          )}
        </>
      )}
      {data?.error && <p className="text-sm text-[var(--muted-foreground)]">{t('research.noNews')}</p>}
    </div>
  )
}

// --------------- Page ---------------

export default function ResearchPage() {
  const t = useTranslations()

  return (
    <SidebarLayout>
      <div className="space-y-4">
        <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
          {t('research.title')}
        </h1>

        <Tabs defaultValue="financials">
          <TabsList variant="line" className="mb-4">
            <TabsTrigger value="financials">{t('research.financials')}</TabsTrigger>
            <TabsTrigger value="geopolitics">{t('research.geopolitics')}</TabsTrigger>
            <TabsTrigger value="northbound">{t('research.northbound')}</TabsTrigger>
            <TabsTrigger value="news">{t('research.news')}</TabsTrigger>
          </TabsList>

          <TabsContent value="financials">
            <FinancialsTab t={t} />
          </TabsContent>
          <TabsContent value="geopolitics">
            <GeopoliticsTab t={t} />
          </TabsContent>
          <TabsContent value="northbound">
            <NorthboundTab t={t} />
          </TabsContent>
          <TabsContent value="news">
            <NewsTab t={t} />
          </TabsContent>
        </Tabs>
      </div>
    </SidebarLayout>
  )
}
