/**
 * In-memory concurrency limiter + queue depth tracker.
 *
 * 01_BUILD_PLAN.md §4.2:
 *   - p-limit max 4 concurrent submissions
 *   - waiting queue max 10 (fail-fast 429 beyond that)
 *   - graceful shutdown — see waitForDrain()
 *
 * Pure JS, no Redis. We only run on a single node; if we ever scale out,
 * swap this module for a Redis-backed queue.
 */

import pLimit from "p-limit";

export const MAX_CONCURRENT = 4;
export const MAX_QUEUED = 10;

const limiter = pLimit(MAX_CONCURRENT);
let pending = 0;

export class QueueFullError extends Error {
  override name = "QueueFullError";
  constructor() {
    super("queue full");
  }
}

export async function withQueueSlot<T>(fn: () => Promise<T>): Promise<T> {
  if (pending >= MAX_QUEUED) throw new QueueFullError();
  pending++;
  try {
    return await limiter(fn);
  } finally {
    pending--;
  }
}

export function getStats(): {
  active: number;
  queued: number;
  pending: number;
} {
  return {
    active: limiter.activeCount,
    queued: limiter.pendingCount,
    pending,
  };
}

/**
 * Wait until every accepted submission has finished. Returns true if drained
 * within the timeout, false otherwise. Useful for SIGTERM handling.
 */
export async function waitForDrain(timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (pending > 0 && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 100));
  }
  return pending === 0;
}
