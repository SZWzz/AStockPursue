import { authHeaders } from "@/lib/apiAuth";

/**
 * Factory that creates an apiFetch wrapper bound to a specific API base path.
 * Replaces the ad-hoc copies that existed in IndicatorLab.tsx and StrategyLab.tsx.
 */
export function createApiFetch(apiBase: string) {
  return async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...authHeaders() as Record<string, string>,
    };
    const res = await fetch(`${apiBase}${path}`, {
      ...options,
      headers: { ...headers, ...((options?.headers as Record<string, string>) || {}) },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
  };
}
