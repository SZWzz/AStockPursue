// frontend/components/financial/SymbolSearch.tsx
'use client'

import { useState } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface SymbolSearchProps {
  onSelect: (symbol: string) => void
  className?: string
}

export function SymbolSearch({ onSelect, className }: SymbolSearchProps) {
  const [query, setQuery] = useState('')

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && query.trim()) {
      onSelect(query.trim().toUpperCase())
    }
  }

  return (
    <div className={cn('relative', className)}>
      <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--foreground-muted)]" />
      <Input
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search symbol..."
        className="pl-7 h-7 text-[12px] bg-[var(--surface-2)] border-[var(--border-default)] w-[180px]"
      />
    </div>
  )
}
