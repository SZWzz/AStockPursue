// frontend/components/strategy-lab/CodeEditor.tsx
'use client'

import { CodeMirror } from '@/components/financial/CodeMirror'

interface CodeEditorProps {
  code: string
  onChange: (value: string | undefined) => void
  language?: string
  height?: string
}

export function CodeEditor({ code, onChange, language = 'python', height = '400px' }: CodeEditorProps) {
  const lang = language === 'javascript' ? 'javascript' : 'python'

  return (
    <div
      className="border border-[var(--border)] rounded-[6px] overflow-hidden"
      style={{ height }}
    >
      <CodeMirror
        value={code}
        language={lang}
        onChange={(v) => onChange(v)}
        className="h-full"
      />
    </div>
  )
}
