import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/auth";

// 303 See Other converts the form POST into a GET on /login. We use a
// relative Location ("/login") so the redirect respects whatever host
// the user reached us at — `NextResponse.redirect(new URL("/login", req.url))`
// would bake the upstream hostname (e.g. `app:3000`) into the redirect,
// which the browser can't follow when fronted by Caddy.
export async function POST(): Promise<NextResponse> {
  const res = new NextResponse(null, {
    status: 303,
    headers: { Location: "/login" },
  });
  res.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return res;
}
