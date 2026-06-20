// frontend/components/financial/LogViewer.tsx
export function LogViewer({ logs }: { logs: string[] }) {
  if (!logs.length) return <div className="text-[12px] text-[var(--foreground-muted)] text-center py-4">No logs</div>
  return (
    <div className="bg-white border border-[var(--border)] rounded-[6px] p-4 h-[200px] overflow-y-auto font-mono text-[13px] leading-relaxed">
      {logs.map((line, i) => <div key={i} className="text-[var(--foreground-secondary)] whitespace-pre-wrap break-all">{line}</div>)}
    </div>
  )
}
