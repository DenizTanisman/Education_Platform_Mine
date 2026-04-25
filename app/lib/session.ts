/**
 * Server-side helpers for reading the current user from the session cookie.
 * Lives in /lib so it's reachable from both server components and route
 * handlers. Returns null on any failure (missing cookie, expired token,
 * deleted user) — call sites pair this with the middleware redirect for
 * pages or with a manual 401 for API routes.
 */
import { cookies } from "next/headers";

import { SESSION_COOKIE, verifySession } from "./auth-edge";
import { prisma } from "./db";

export type CurrentUser = {
  id: string;
  email: string;
  role: "STUDENT" | "ADMIN";
};

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const claims = await verifySession(token);
  if (!claims) return null;
  const user = await prisma.user.findUnique({
    where: { id: claims.sub },
    select: { id: true, email: true, role: true },
  });
  return user;
}

export async function requireUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) throw new Error("unauthenticated");
  return user;
}
