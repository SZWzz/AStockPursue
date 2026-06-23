'use client'

import { useState, useEffect } from 'react'
import { StrategyCard } from '@/components/financial/StrategyCard'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'

interface Template {
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

const CATEGORIES = [
  { key: 'all', label: '全部' },
  { key: 'trend', label: '趋势跟踪' },
  { key: 'mean_reversion', label: '均值回归' },
  { key: 'momentum', label: '动量' },
  { key: 'volatility', label: '波动率' },
  { key: 'volume', label: '成交量' },
  { key: 'multi_factor', label: '多因子' },
]

export function MarketplaceContent() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [activeCategory, setActiveCategory] = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/v1/marketplace/templates')
      .then(r => r.json())
      .then(data => {
        setTemplates(data.templates || data)
      })
      .catch(() => {
        // Fallback: could load from static JSON
      })
      .finally(() => setLoading(false))
  }, [])

  const filtered = activeCategory === 'all'
    ? templates
    : templates.filter(t => t.category === activeCategory)

  const handleInstall = (template: Template) => {
    toast.success(`正在安装 ${template.name}...`)
    // TODO: POST to install API
  }

  if (loading) return null // Suspense handles loading

  return (
    <div className="space-y-4">
      {/* Category tabs */}
      <Tabs value={activeCategory} onValueChange={setActiveCategory}>
        <TabsList className="w-full justify-start border-b border-[var(--border)] rounded-none bg-transparent p-0 h-auto gap-0 overflow-x-auto">
          {CATEGORIES.map(cat => (
            <TabsTrigger
              key={cat.key}
              value={cat.key}
              className="text-[13px] px-4 py-2.5 border-b-2 border-transparent data-[state=active]:border-[var(--primary)] data-[state=active]:text-[var(--primary)] data-[state=active]:shadow-none rounded-none bg-transparent hover:text-[var(--foreground)] shrink-0"
            >
              {cat.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(template => (
          <StrategyCard
            key={template.key}
            template={template}
            onInstall={() => handleInstall(template)}
          />
        ))}
      </div>

      {filtered.length === 0 && !loading && (
        <div className="text-center py-16 text-[13px] text-[var(--foreground-muted)]">
          该分类下暂无策略模板
        </div>
      )}
    </div>
  )
}
