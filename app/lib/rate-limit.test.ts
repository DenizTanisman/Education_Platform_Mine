import { strict as assert } from "node:assert";
import { afterEach, describe, test } from "node:test";

import { _reset, ipFromHeaders, rateLimit } from "./rate-limit.ts";

afterEach(() => _reset());

describe("rateLimit (sliding window)", () => {
  test("allows up to N hits then blocks", () => {
    const now = 1_000_000;
    for (let i = 0; i < 5; i++) {
      const r = rateLimit("k", 5, 60_000, now + i);
      assert.ok(r.ok, `hit ${i + 1}/5 should pass`);
    }
    const sixth = rateLimit("k", 5, 60_000, now + 6);
    assert.equal(sixth.ok, false);
    assert.ok(sixth.retryAfterMs > 0);
  });

  test("expired hits drop off the window", () => {
    const start = 1_000_000;
    rateLimit("k", 2, 1_000, start);
    rateLimit("k", 2, 1_000, start + 100);
    // window is 1s; jumping past it should re-open the budget
    const r = rateLimit("k", 2, 1_000, start + 2_000);
    assert.ok(r.ok);
  });

  test("different keys are independent", () => {
    const t = 1_000_000;
    for (let i = 0; i < 5; i++) rateLimit("a", 5, 60_000, t + i);
    const r = rateLimit("b", 5, 60_000, t);
    assert.ok(r.ok);
  });
});

describe("ipFromHeaders", () => {
  test("prefers x-forwarded-for first hop", () => {
    const h = new Headers({ "x-forwarded-for": "1.2.3.4, 10.0.0.1" });
    assert.equal(ipFromHeaders(h), "1.2.3.4");
  });
  test("falls back to x-real-ip", () => {
    const h = new Headers({ "x-real-ip": "5.6.7.8" });
    assert.equal(ipFromHeaders(h), "5.6.7.8");
  });
  test("returns 'unknown' if neither is set", () => {
    assert.equal(ipFromHeaders(new Headers()), "unknown");
  });
});
