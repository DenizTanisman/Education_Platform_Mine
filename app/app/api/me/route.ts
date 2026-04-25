import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import {
  maybeRefresh,
  SESSION_COOKIE,
  SESSION_COOKIE_OPTIONS,
  verifySession,
} from "@/lib/auth";
import { prisma } from "@/lib/db";

export async function GET(): Promise<NextResponse> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const claims = await verifySession(token);
  if (!claims) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const user = await prisma.user.findUnique({
    where: { id: claims.sub },
    select: { id: true, email: true, role: true, createdAt: true },
  });
  if (!user) {
    // session JWT is valid but the user has been deleted — treat as logged out
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const res = NextResponse.json(user);
  const refreshed = await maybeRefresh(claims);
  if (refreshed) {
    res.cookies.set(SESSION_COOKIE, refreshed, SESSION_COOKIE_OPTIONS);
  }
  return res;
}
