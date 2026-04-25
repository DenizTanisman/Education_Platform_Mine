/**
 * Node-runtime auth primitives — bcrypt password hashing + JWT signing.
 * Verification + cookie name + types come from `auth-edge.ts`, which is
 * the only thing middleware imports (bcryptjs is incompatible with the
 * edge runtime).
 *
 * Faz 5.1 (01_BUILD_PLAN.md):
 *  - JWT sign/verify with httpOnly cookie
 *  - bcrypt cost 12
 *  - Timing-safe password compare (bcrypt.compare is timing-safe)
 *  - Session expiry: 7 days, sliding renewal (refresh on read)
 */

import bcrypt from "bcryptjs";
import { SignJWT } from "jose";

import {
  SESSION_COOKIE as _SESSION_COOKIE,
  type SessionClaims,
  type UserRole,
  verifySession as _verifySession,
  _resetKeyCache as _resetEdgeKey,
} from "./auth-edge";

const BCRYPT_COST = 12;
const SEVEN_DAYS_S = 7 * 24 * 60 * 60;
const SLIDING_REFRESH_THRESHOLD_S = 24 * 60 * 60; // refresh in last 24h

export const SESSION_COOKIE = _SESSION_COOKIE;
export const verifySession = _verifySession;
export type { SessionClaims, UserRole };

let _signKey: Uint8Array | null = null;
function key(): Uint8Array {
  if (_signKey) return _signKey;
  const secret = process.env.JWT_SECRET ?? "";
  if (secret.length < 32) {
    throw new Error("JWT_SECRET is required and must be at least 32 chars");
  }
  _signKey = new TextEncoder().encode(secret);
  return _signKey;
}

// Test-only: clear both this module's signing key cache AND the edge
// module's verification key cache, so a JWT_SECRET swap takes effect.
export function _resetKeyCache(): void {
  _signKey = null;
  _resetEdgeKey();
}

export async function hashPassword(plaintext: string): Promise<string> {
  if (plaintext.length < 8) throw new Error("password too short");
  return bcrypt.hash(plaintext, BCRYPT_COST);
}

export async function verifyPassword(
  plaintext: string,
  hash: string,
): Promise<boolean> {
  return bcrypt.compare(plaintext, hash);
}

export async function signSession(args: {
  userId: string;
  role: UserRole;
}): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ role: args.role })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setSubject(args.userId)
    .setIssuedAt(now)
    .setExpirationTime(now + SEVEN_DAYS_S)
    .sign(key());
}

/**
 * Returns a fresh token if `claims` is within `SLIDING_REFRESH_THRESHOLD_S`
 * of expiry, otherwise null. Caller decides whether to set the cookie.
 */
export async function maybeRefresh(claims: SessionClaims): Promise<string | null> {
  const now = Math.floor(Date.now() / 1000);
  const remaining = claims.exp - now;
  if (remaining > SLIDING_REFRESH_THRESHOLD_S) return null;
  return signSession({ userId: claims.sub, role: claims.role });
}

export const SESSION_COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: "lax" as const,
  path: "/",
  // secure: true in production. Caddy terminates TLS; behind it the app
  // sees plain HTTP, so we cannot blindly set secure=true.
  secure: process.env.NODE_ENV === "production",
  maxAge: SEVEN_DAYS_S,
};
