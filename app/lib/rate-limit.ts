/**
 * In-memory sliding-window rate limiter, keyed by (route, identifier).
 * Per 01_BUILD_PLAN.md §5.2: register + login at most 5 requests / hour
 * per IP. Single-process only — fine for a single-host Compose deploy;
 * swap to Redis if we ever scale out.
 *
 * The window is *sliding*: we keep timestamps of recent hits and discard
 * any older than `windowMs` on each check. Memory is O(N * limit) where
 * N is distinct keys; a periodic sweep keeps unused keys from leaking.
 */

const HITS = new Map<string, number[]>();
const SWEEP_INTERVAL_MS = 5 * 60 * 1000;
let _sweepTimer: NodeJS.Timeout | null = null;

export interface RateLimitResult {
  ok: boolean;
  remaining: number;
  retryAfterMs: number;
}

export function rateLimit(
  key: string,
  limit: number,
  windowMs: number,
  now: number = Date.now(),
): RateLimitResult {
  ensureSweep(windowMs);
  const cutoff = now - windowMs;
  const list = (HITS.get(key) ?? []).filter((t) => t > cutoff);
  if (list.length >= limit) {
    const oldest = list[0]!;
    return {
      ok: false,
      remaining: 0,
      retryAfterMs: Math.max(0, oldest + windowMs - now),
    };
  }
  list.push(now);
  HITS.set(key, list);
  return { ok: true, remaining: limit - list.length, retryAfterMs: 0 };
}

function ensureSweep(windowMs: number): void {
  if (_sweepTimer !== null) return;
  _sweepTimer = setInterval(() => {
    const cutoff = Date.now() - windowMs * 4;
    for (const [k, ts] of HITS) {
      const filtered = ts.filter((t) => t > cutoff);
      if (filtered.length === 0) HITS.delete(k);
      else HITS.set(k, filtered);
    }
  }, SWEEP_INTERVAL_MS);
  if (typeof _sweepTimer.unref === "function") _sweepTimer.unref();
}

// Test-only.
export function _reset(): void {
  HITS.clear();
  if (_sweepTimer !== null) {
    clearInterval(_sweepTimer);
    _sweepTimer = null;
  }
}

/**
 * Conservative IP extraction. Trusts X-Forwarded-For only when there's a
 * single hop (Caddy → app). Multiple hops are flattened to the first
 * address. Falls back to a static "unknown" — that bucket gets clipped
 * fast under load, which is fine: anonymous traffic shouldn't hammer auth.
 */
export function ipFromHeaders(h: Headers): string {
  const xff = h.get("x-forwarded-for");
  if (xff) {
    const first = xff.split(",")[0]?.trim();
    if (first) return first;
  }
  const real = h.get("x-real-ip");
  if (real) return real;
  return "unknown";
}
