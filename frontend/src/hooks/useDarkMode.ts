import { useEffect } from "react";

/**
 * OLED terminal is always dark. This hook exists for backward compatibility
 * — components that call useDarkMode() will always receive dark=true.
 * The toggle is a no-op (can be restored if light mode is re-added later).
 */
export function useDarkMode() {
  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  return {
    dark: true as const,
    toggle: () => {
      // No-op: OLED terminal is always dark
    },
  };
}
