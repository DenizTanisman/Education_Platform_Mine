import { NextResponse } from "next/server";
import { z } from "zod";

import {
  hashPassword,
  signSession,
  SESSION_COOKIE,
  SESSION_COOKIE_OPTIONS,
} from "@/lib/auth";
import { prisma } from "@/lib/db";
import { ipFromHeaders, rateLimit } from "@/lib/rate-limit";

const Body = z.object({
  email: z.string().email().max(254).toLowerCase(),
  password: z.string().min(8).max(256),
});

const HOUR_MS = 60 * 60 * 1000;
const PER_IP_LIMIT = 5;

export async function POST(req: Request): Promise<NextResponse> {
  const ip = ipFromHeaders(req.headers);
  const limit = rateLimit(`register:${ip}`, PER_IP_LIMIT, HOUR_MS);
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

  const existing = await prisma.user.findUnique({
    where: { email: parsed.data.email },
    select: { id: true },
  });
  if (existing) {
    // Vague to avoid email enumeration.
    return NextResponse.json({ error: "registration_failed" }, { status: 409 });
  }

  const passwordHash = await hashPassword(parsed.data.password);
  const user = await prisma.user.create({
    data: {
      email: parsed.data.email,
      passwordHash,
      role: "STUDENT",
    },
  });

  const token = await signSession({ userId: user.id, role: user.role });
  const res = NextResponse.json({ id: user.id, email: user.email, role: user.role });
  res.cookies.set(SESSION_COOKIE, token, SESSION_COOKIE_OPTIONS);
  return res;
}
