// frontend/components/financial/DividerSection.tsx
interface DividerSectionProps {
  title: string
  className?: string
}

export function DividerSection({ title, className }: DividerSectionProps) {
  return (
    <div className={`bg-[var(--surface-1)] px-6 py-2 ${className || ''}`}>
      <span className="text-[12px] font-semibold text-[var(--foreground-secondary)]">
        {title}
      </span>
    </div>
  )
}
