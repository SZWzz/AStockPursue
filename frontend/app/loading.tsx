// frontend/app/loading.tsx
export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
        <span className="text-[13px] text-[var(--foreground-muted)]">Loading...</span>
      </div>
    </div>
  )
}
