/**
 * Framework-agnostic SSE utilities: dedup, reconnect scheduling, URL building.
 */

export interface DedupTracker {
  track: (eventId: string) => boolean; // true = duplicate
  reset: () => void;
}

export function createDedupTracker(capacity = 500): DedupTracker {
  const seen = new Set<string>();
  const order: string[] = [];

  return {
    track(eventId: string): boolean {
      if (!eventId) return false;
      if (seen.has(eventId)) return true;
      seen.add(eventId);
      order.push(eventId);
      if (order.length > capacity) {
        const oldest = order.shift()!;
        seen.delete(oldest);
      }
      return false;
    },
    reset() {
      seen.clear();
      order.length = 0;
    },
  };
}

export interface ReconnectConfig {
  initialRetryMs?: number;
  maxRetryMs?: number;
  backoffFactor?: number;
}

const RECONNECT_DEFAULTS: Required<ReconnectConfig> = {
  initialRetryMs: 1000,
  maxRetryMs: 30000,
  backoffFactor: 2,
};

export function calcReconnectDelay(retryCount: number, config?: ReconnectConfig): number {
  const { initialRetryMs, maxRetryMs, backoffFactor } = { ...RECONNECT_DEFAULTS, ...config };
  const base = Math.min(
    initialRetryMs * Math.pow(backoffFactor, retryCount),
    maxRetryMs,
  );
  // Add jitter: ±25% random to avoid thundering herd
  const jitter = base * 0.25 * (Math.random() * 2 - 1);
  return Math.round(base + jitter);
}

export function scheduleReconnect(
  cb: () => void,
  retryCount: number,
  config?: ReconnectConfig,
): ReturnType<typeof setTimeout> {
  const delay = calcReconnectDelay(retryCount, config);
  return setTimeout(cb, delay);
}

export function buildReconnectUrl(baseUrl: string, lastEventId: string | null): string {
  if (!lastEventId) return baseUrl;
  const sep = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${sep}Last-Event-ID=${encodeURIComponent(lastEventId)}`;
}
