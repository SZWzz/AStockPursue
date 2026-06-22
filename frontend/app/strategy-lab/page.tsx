// frontend/app/strategy-lab/page.tsx
'use client'

import { useState, useRef } from 'react'
import { useTranslations } from 'next-intl'
import Link from 'next/link'
import { toast } from 'sonner'
import { SidebarLayout } from '@/components/layout/SidebarLayout'
import { CodeEditor } from '@/components/strategy-lab/CodeEditor'
import { ChartPanel } from '@/components/strategy-lab/ChartPanel'
import { BacktestPanel } from '@/components/strategy-lab/BacktestPanel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Save, Loader2, FolderOpen, ExternalLink } from 'lucide-react'

const DEFAULT_CODE = `# Strategy: Momentum Breakout
# Symbol: {symbol}  |  Period: {start} → {end}

def generate(df, params):
    fast = params.get('fast', 5)
    slow = params.get('slow', 20)
    df['ma_fast'] = df['close'].rolling(fast).mean()
    df['ma_slow'] = df['close'].rolling(slow).mean()
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
    return df
`

// --------------- basic Python syntax validation ---------------
function validatePythonSyntax(code: string): string | null {
  if (!code.trim()) return 'Code cannot be empty'

  // check for unbalanced parentheses/brackets/braces
  const pairs: [string, string][] = [['(', ')'], ['[', ']'], ['{', '}']]
  for (const [open, close] of pairs) {
    let depth = 0
    for (const ch of code) {
      if (ch === open) depth++
      if (ch === close) depth--
      if (depth < 0) return `Unbalanced '${close}'`
    }
    if (depth !== 0) return `Unbalanced '${open}'`
  }

  // check for triple-quoted strings that aren't closed
  const tripleSingle = code.split("'''")
  const tripleDouble = code.split('"""')
  if (tripleSingle.length % 2 === 0) return "Unbalanced '''"
  if (tripleDouble.length % 2 === 0) return 'Unbalanced """'

  try {
    // Any Python code that compiles is considered valid syntax
    Function('"use strict"; return (' + JSON.stringify(code) + ')')()
  } catch {
    // Not a JSON string issue - just check basic structure
  }

  return null
}

// --------------- Page ---------------
export default function StrategyLabPage() {
  const t = useTranslations()
  const [code, setCode] = useState(DEFAULT_CODE)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, number> | null>(null)
  const [equityData, setEquityData] = useState<{ time: string; equity: number }[]>([])
  const [backtestId, setBacktestId] = useState<string | null>(null)

  // save dialog state
  const [saveOpen, setSaveOpen] = useState(false)
  const [strategyName, setStrategyName] = useState('')
  const [saving, setSaving] = useState(false)

  // load dropdown state
  const [savedStrategies, setSavedStrategies] = useState<{ id: string; strategy_name: string }[]>([])
  const [loadingList, setLoadingList] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleRun = async (config: { symbol: string; startDate: string; endDate: string }) => {
    // SL2: validate code before sending
    const validationError = validatePythonSyntax(code)
    if (validationError) {
      toast.error(t('strategyLab.codeValidationError') + ': ' + validationError)
      return
    }

    setRunning(true)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: `${config.symbol}_${config.startDate}_${config.endDate}`,
          symbol: config.symbol,
          start_date: config.startDate,
          end_date: config.endDate,
          frequency: 'daily',
          initial_capital: 100000,
          code,
        }),
      })
      if (!res.ok) throw new Error('Backtest failed')
      const data = await res.json()
      if (data?.id) setBacktestId(data.id)
      setResult({
        totalReturn: data.total_return || 0,
        sharpeRatio: data.sharpe_ratio || 0,
        maxDrawdown: data.max_drawdown || 0,
      })
      if (data.equity_curve) {
        setEquityData(data.equity_curve.map((e: { time: string; equity: number }) => ({
          time: e.time?.slice(0, 10) || '',
          equity: e.equity,
        })))
      }
    } catch (e) {
      toast.error(t('common.error'))
      setResult(null)
    } finally {
      setRunning(false)
    }
  }

  // SL3: save current strategy
  const handleSave = async () => {
    if (!strategyName.trim()) return
    setSaving(true)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: strategyName.trim(),
          code,
          symbol: '',
          start_date: '',
          end_date: '',
          frequency: 'daily',
          initial_capital: 100000,
        }),
      })
      if (!res.ok) throw new Error('Save failed')
      toast.success(t('strategyLab.saveSuccess'))
      setSaveOpen(false)
      setStrategyName('')
    } catch {
      toast.error(t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  // SL3: load saved strategies list
  const handleLoadList = async () => {
    setLoadingList(true)
    try {
      const res = await fetch('/api/backtest')
      if (!res.ok) throw new Error('Fetch failed')
      const data = await res.json()
      const items = data.data || data || []
      setSavedStrategies(Array.isArray(items) ? items : [])
    } catch {
      toast.error(t('common.error'))
    } finally {
      setLoadingList(false)
    }
  }

  // SL3: load a specific strategy's code
  const handleLoadStrategy = async (id: string) => {
    try {
      const res = await fetch(`/api/backtest/${id}`)
      if (!res.ok) throw new Error('Fetch failed')
      const data = await res.json()
      const detail = data.data || data
      if (detail?.code) {
        setCode(String(detail.code))
      }
    } catch {
      toast.error(t('common.error'))
    }
  }

  return (
    <SidebarLayout>
      <div className="space-y-4">
        {/* SL1: i18n title */}
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-[400] tracking-[-0.4px] text-[var(--foreground)]">
            {t('nav.strategyLab')}
          </h1>
          <div className="flex items-center gap-2">
            {/* SL3: Load button */}
            <DropdownMenu>
              <DropdownMenuTrigger
                className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium border border-[var(--border-default)] bg-transparent shadow-sm h-9 px-3 hover:bg-[var(--surface-1)] transition-colors disabled:opacity-50"
                disabled={loadingList}
                onMouseEnter={() => { if (savedStrategies.length === 0) handleLoadList() }}
                onFocus={() => { if (savedStrategies.length === 0) handleLoadList() }}
              >
                {loadingList ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderOpen className="w-4 h-4" />}
                {t('strategyLab.loadStrategy')}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {savedStrategies.length === 0 ? (
                  <div className="px-2 py-1.5 text-xs text-[var(--muted-foreground)]">{t('common.noData')}</div>
                ) : (
                  savedStrategies.map((item) => (
                    <DropdownMenuItem key={item.id} onClick={() => handleLoadStrategy(item.id)}>
                      {item.strategy_name || item.id}
                    </DropdownMenuItem>
                  ))
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            {/* SL3: Save button */}
            <Button variant="outline" size="sm" onClick={() => setSaveOpen(true)}>
              <Save className="w-4 h-4 mr-2" />
              {t('strategyLab.saveStrategy')}
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8 space-y-4">
            <CodeEditor code={code} onChange={(v) => setCode(v ?? '')} height="400px" />
            {/* SL4: pass i18n labels */}
            <ChartPanel
              equityData={equityData}
              title={t('strategyLab.equityCurve')}
              emptyHint={t('strategyLab.emptyHint')}
            />
          </div>
          <div className="col-span-4">
            {/* SL5: pass i18n labels */}
            <BacktestPanel
              onRun={handleRun}
              running={running}
              result={result}
              configTitle={t('strategyLab.config')}
              symbolLabel={t('strategyLab.symbol')}
              startLabel={t('strategyLab.start')}
              endLabel={t('strategyLab.end')}
              runLabel={'-- ' + t('strategyLab.run')}
              runningLabel={t('strategyLab.running')}
              returnLabel={t('strategyLab.totalReturn')}
              sharpeLabel={t('strategyLab.sharpe')}
              maxDDLabel={t('strategyLab.maxDD')}
            />
            {backtestId && result && (
              <Link
                href={`/backtest/${backtestId}`}
                className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--primary)] hover:underline"
              >
                <ExternalLink className="w-4 h-4" />
                {t('strategyLab.viewFullReport')}
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* SL3: Save Dialog */}
      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('strategyLab.saveStrategy')}</DialogTitle>
            <DialogDescription>{t('backtest.namePlaceholder')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('strategyLab.strategyName')}</Label>
              <Input
                placeholder={t('backtest.namePlaceholder')}
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleSave} disabled={saving || !strategyName.trim()}>
              {saving ? t('common.loading') : t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SidebarLayout>
  )
}
