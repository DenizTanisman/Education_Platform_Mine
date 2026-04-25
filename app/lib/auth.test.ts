/**
 * Auth library unit tests. Pure crypto-level — no DB, no HTTP.
 */
import { strict as assert } from "node:assert";
import { afterEach, beforeEach, describe, test } from "node:test";

const VALID_SECRET = "x".repeat(32);

beforeEach(() => {
  process.env.JWT_SECRET = VALID_SECRET;
});

describe("password hashing", () => {
  test("hashPassword + verifyPassword round-trip", async () => {
    const { hashPassword, verifyPassword } = await import("./auth.ts");
    const h = await hashPassword("supersecret");
    assert.notEqual(h, "supersecret");
    assert.ok(await verifyPassword("supersecret", h));
    assert.ok(!(await verifyPassword("wrong-pass", h)));
  });

  test("rejects passwords shorter than 8 chars", async () => {
    const { hashPassword } = await import("./auth.ts");
    await assert.rejects(hashPassword("short"));
  });
});

describe("session JWT", () => {
  test("sign + verify round-trip", async () => {
    const { signSession, verifySession } = await import("./auth.ts");
    const token = await signSession({ userId: "u1", role: "STUDENT" });
    const claims = await verifySession(token);
    assert.ok(claims, "claims should not be null");
    if (!claims) return;
    assert.equal(claims.sub, "u1");
    assert.equal(claims.role, "STUDENT");
    assert.ok(claims.exp > claims.iat);
  });

  test("verifySession returns null for tampered token", async () => {
    const { signSession, verifySession } = await import("./auth.ts");
    const token = await signSession({ userId: "u1", role: "STUDENT" });
    const bad = token.slice(0, -2) + "AA";
    assert.equal(await verifySession(bad), null);
  });

  test("verifySession returns null for token signed with a different secret", async () => {
    const { signSession, _resetKeyCache } = await import("./auth.ts");
    const token = await signSession({ userId: "u1", role: "STUDENT" });
    process.env.JWT_SECRET = "y".repeat(32);
    _resetKeyCache();
    const { verifySession } = await import("./auth.ts");
    assert.equal(await verifySession(token), null);
  });

  test("rejects insufficient JWT_SECRET length", async () => {
    process.env.JWT_SECRET = "short";
    const { signSession, _resetKeyCache } = await import("./auth.ts");
    _resetKeyCache();
    await assert.rejects(signSession({ userId: "u1", role: "STUDENT" }));
  });
});

describe("sliding refresh", () => {
  afterEach(async () => {
    const { _resetKeyCache } = await import("./auth.ts");
    process.env.JWT_SECRET = VALID_SECRET;
    _resetKeyCache();
  });

  test("returns null when token is far from expiry", async () => {
    const { signSession, verifySession, maybeRefresh } = await import(
      "./auth.ts"
    );
    const token = await signSession({ userId: "u1", role: "STUDENT" });
    const claims = await verifySession(token);
    assert.ok(claims);
    if (!claims) return;
    assert.equal(await maybeRefresh(claims), null);
  });

  test("returns a new token when within the threshold", async () => {
    const { maybeRefresh, verifySession } = await import("./auth.ts");
    const now = Math.floor(Date.now() / 1000);
    const claimsAboutToExpire = {
      sub: "u1",
      role: "STUDENT" as const,
      iat: now,
      exp: now + 60,
    };
    const refreshed = await maybeRefresh(claimsAboutToExpire);
    assert.ok(refreshed, "expected a refreshed token");
    if (!refreshed) return;
    const newClaims = await verifySession(refreshed);
    assert.ok(newClaims);
    if (!newClaims) return;
    assert.ok(newClaims.exp - now > 60 * 60 * 24);
  });
});
