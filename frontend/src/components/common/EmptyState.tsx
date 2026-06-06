/**
 * EmptyState — reusable placeholder for pages with no content.
 *
 * Provides a consistent icon + title + description + optional action button
 * pattern across all pages.  Used when lists are empty, searches return no
 * results, or a feature hasn't been configured yet.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  /** Lucide icon component (e.g. `<FolderOpen />`). */
  icon?: ReactNode;
  /** Primary message (e.g. "No projects yet"). */
  title?: string;
  /** Secondary hint/instruction text. */
  description?: string;
  /** Optional CTA button rendered below the description. */
  action?: ReactNode;
  /** Extra class for the outer container. */
  className?: string;
  /** Size variant: "sm" (inline, compact) or "lg" (full-page centred). */
  size?: "sm" | "lg";
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  size = "lg",
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center px-4",
        size === "lg" ? "py-16 gap-3" : "py-6 gap-2",
        className,
      )}
    >
      {icon && (
        <div className={cn(
          "text-muted-foreground/40",
          size === "lg" ? "mb-1" : "",
        )}>
          {icon}
        </div>
      )}
      {title && (
        <p className={cn(
          "font-medium text-muted-foreground",
          size === "lg" ? "text-sm" : "text-xs",
        )}>
          {title}
        </p>
      )}
      {description && (
        <p className={cn(
          "text-muted-foreground/60 max-w-sm",
          size === "lg" ? "text-xs" : "text-[11px]",
        )}>
          {description}
        </p>
      )}
      {action && (
        <div className={size === "lg" ? "mt-2" : "mt-1"}>
          {action}
        </div>
      )}
    </div>
  );
}
