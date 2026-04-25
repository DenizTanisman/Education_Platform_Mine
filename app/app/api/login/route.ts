import { NextResponse } from "next/server";
import { z } from "zod";

import {
  signSession,
  SESSION_COOKIE,
  SESSION_COOKIE_OPTIONS,
  verifyPassword,
} from "@/lib/auth";
import { prisma } from "@/lib/db";
import { ipFromHeaders, rateLimit } from "@/lib/rate-limit";

const Body = z.object({
  email: z.string().email().max(254).toLowerCase(),
  password: z.string().min(1).max(256),
});

const HOUR_MS = 60 * 60 * 1000;
const PER_IP_LIMIT = 5;

export async function POST(req: Request): Promise<NextResponse> {
  const ip = ipFromHeaders(req.headers);
  const limit = rateLimit(`login:${ip}`, PER_IP_LIMIT, HOUR_MS);
  if (!limit.ok) {
    return NextResponse.json(
      { error: "too_many_requests" },
      {
        status: 429,
        headers: { "retry-after": Math.ceil(limit.retryAfterMs / 1000).toString() },
      },
    );
  }

  const json = await req.json().catch(() => null);
  const parsed = Body.safeParse(json);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { email: parsed.data.email },
  });
  // Same response shape regardless of whether the email exists, so probing
  // for valid accounts is no faster than testing arbitrary passwords.
  if (!user || !(await verifyPassword(parsed.data.password, user.passwordHash))) {
    return NextResponse.json({ error: "invalid_credentials" }, { status: 401 });
  }

  const token = await signSession({ userId: user.id, role: user.role });
  const res = NextResponse.json({ id: user.id, email: user.email, role: user.role });
  res.cookies.set(SESSION_COOKIE, token, SESSION_COOKIE_OPTIONS);
  return res;
}
