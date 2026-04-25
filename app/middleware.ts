/**
 * Edge middleware: gate protected routes by JWT presence, route admins
 * away from /admin/* if their session lacks ADMIN role.
 *
 * Public paths: /, /login, /register, /api/healthz, /api/login, /api/register, /_next, static assets.
 * Everything else requires a valid session.
 */

import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE, verifySession } from "@/lib/auth-edge";

const PUBLIC_PREFIXES = ["/_next/", "/static/", "/pdfs/", "/favicon"];
const PUBLIC_PATHS = new Set([
  "/",
  "/login",
  "/register",
  "/api/login",
  "/api/register",
  "/api/healthz",
]);

export async function middleware(req: NextRequest): Promise<NextResponse> {
  const { pathname } = req.nextUrl;
  if (
    PUBLIC_PATHS.has(pathname) ||
    PUBLIC_PREFIXES.some((p) => pathname.startsWith(p))
  ) {
    return NextResponse.next();
  }

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  const claims = token ? await verifySession(token) : null;

  if (!claims) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
    }
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (pathname.startsWith("/admin") && claims.role !== "ADMIN") {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }
  if (pathname.startsWith("/api/admin") && claims.role !== "ADMIN") {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Skip static assets and the Next image optimizer; everything else
    // hits the middleware.
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
