import { useEffect, useRef, useState } from "react";

interface UseCountUpOptions {
  /** Target value to animate to */
  to: number;
  /** Animation duration in ms (default: 200) */
  duration?: number;
  /** Start from this value (default: 0) */
  from?: number;
  /** Decimals to display (default: 0) */
  decimals?: number;
  /** Only animate when this is true */
  enabled?: boolean;
}

/**
 * Animate a number from `from` to `to` over `duration` ms.
 * Uses requestAnimationFrame for smooth 60fps counting with ease-out cubic.
 * Respects prefers-reduced-motion: instantly snaps to `to`.
 */
export function useCountUp({
  to,
  duration = 200,
  from = 0,
  decimals = 0,
  enabled = true,
}: UseCountUpOptions): number {
  const [value, setValue] = useState(from);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const startValueRef = useRef(from);

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!enabled || prefersReduced) {
      setValue(to);
      startValueRef.current = to;
      return;
    }

    startValueRef.current = value;
    startTimeRef.current = null;

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValueRef.current + (to - startValueRef.current) * eased;

      setValue(Number(current.toFixed(decimals)));

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [to, duration, decimals, enabled]);

  return value;
}
