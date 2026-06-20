// frontend/components/financial/CodeMirror.tsx — Reusable CodeMirror 6 wrapper
'use client'

import { useEffect, useRef } from 'react'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers } from '@codemirror/view'
import { oneDark } from '@codemirror/theme-one-dark'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'

interface CodeMirrorProps {
  value: string
  readOnly?: boolean
  language?: 'python' | 'javascript'
  onChange?: (value: string) => void
  className?: string
}

export function CodeMirror({ value, readOnly = false, language = 'python', onChange, className }: CodeMirrorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const langExtension = language === 'javascript' ? javascript() : python()

    const extensions = [
      langExtension,
      oneDark,
      lineNumbers(),
      EditorView.editable.of(!readOnly),
      EditorView.theme({
        '&': { height: '100%' },
        '.cm-scroller': { overflow: 'auto', fontFamily: "var(--font-mono)", fontSize: '13px' },
        '.cm-content': { padding: '12px' },
        '.cm-gutters': { backgroundColor: 'var(--surface-1)', color: 'var(--foreground-muted)', borderRight: '1px solid var(--border-subtle)' },
      }),
    ]

    if (onChange) {
      extensions.push(
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            onChange(update.state.doc.toString())
          }
        })
      )
    }

    const state = EditorState.create({
      doc: value,
      extensions,
    })

    const view = new EditorView({
      state,
      parent: containerRef.current,
    })

    viewRef.current = view

    return () => {
      view.destroy()
      viewRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Update content when value prop changes externally
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const currentDoc = view.state.doc.toString()
    if (value !== currentDoc) {
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: value },
      })
    }
  }, [value])

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ minHeight: '200px', height: '100%' }}
    />
  )
}
