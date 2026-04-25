/**
 * Edge-runtime-safe subset of the auth library — JWT only, no bcrypt.
 *
 * `app/middleware.ts` runs in edge runtime and only needs to verify the
 * session cookie. Importing the full `lib/auth.ts` from middleware would
 * pull bcryptjs into the edge bundle, which uses setImmediate /
 * process.nextTick and breaks the build. This module is therefore the
 * only thing middleware imports from `lib/`.
 */

import { jwtVerify } from "jose";

export const SESSION_COOKIE = "iau_session";

export type UserRole = "STUDENT" | "ADMIN";

export interface SessionClaims {
  sub: string;
  role: UserRole;
  iat: number;
  exp: number;
}

let _key: Uint8Array | null = null;
function key(): Uint8Array {
  if (_key) return _key;
  const secret = process.env.JWT_SECRET ?? "";
  if (secret.length < 32) {
    throw new Error("JWT_SECRET is required and must be at least 32 chars");
  }
  _key = new TextEncoder().encode(secret);
  return _key;
}

export async function verifySession(token: string): Promise<SessionClaims | null> {
  try {
    const { payload } = await jwtVerify(token, key(), {
      algorithms: ["HS256"],
    });
    if (
      typeof payload.sub !== "string" ||
      typeof payload.iat !== "number" ||
      typeof payload.exp !== "number" ||
      (payload.role !== "STUDENT" && payload.role !== "ADMIN")
    ) {
      return null;
    }
    return {
      sub: payload.sub,
      role: payload.role,
      iat: payload.iat,
      exp: payload.exp,
    };
  } catch {
    return null;
  }
}

export function _resetKeyCache(): void {
  _key = null;
}
