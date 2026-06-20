// frontend/components/strategy-lab/CodeEditor.tsx
'use client'

import dynamic from 'next/dynamic'

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

interface CodeEditorProps {
  code: string
  onChange: (value: string | undefined) => void
  language?: string
  height?: string
}

export function CodeEditor({ code, onChange, language = 'python', height = '400px' }: CodeEditorProps) {
  return (
    <div className="border border-[var(--border)] rounded-[6px] overflow-hidden">
      <MonacoEditor
        height={height}
        language={language}
        value={code}
        onChange={onChange}
        theme="vs"
        options={{
          fontSize: 13,
          fontFamily: 'var(--font-mono)',
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          lineNumbers: 'on',
          renderLineHighlight: 'line',
          tabSize: 4,
        }}
      />
    </div>
  )
}
