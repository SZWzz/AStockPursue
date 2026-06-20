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
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
      <Input
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search symbol..."
        className="pl-9 pr-4 h-10 w-full rounded-[6px] border border-[var(--border)] bg-white text-[14px] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
      />
    </div>
  )
}
