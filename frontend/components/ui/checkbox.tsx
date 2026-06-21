"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

function Checkbox({
  checked,
  onCheckedChange,
  className,
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, 'checked' | 'onChange'> & {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}) {
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      className={cn(
        "h-4 w-4 rounded border border-[var(--border-default)] bg-transparent accent-[var(--primary)] cursor-pointer",
        className
      )}
      {...props}
    />
  )
}

export { Checkbox }
