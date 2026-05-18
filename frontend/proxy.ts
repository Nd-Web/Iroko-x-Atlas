/**
 * proxy.ts  (Next.js 16 — replaces middleware.ts)
 *
 * Route protection layer for Iroko AI.
 *
 * Rules:
 * 1. Any user WITHOUT a token that tries to reach a protected route → /login
 * 2. Any user WITH a token that tries to reach /login or /forgot-password → /dashboard
 * 3. The invite flow (/invite) is always public — users arrive from email links.
 * 4. API routes, static assets, and _next internals are always let through.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Inlined here because proxy.ts is bundled independently by Next.js and
// relative imports from outside this file are not reliably resolved.
const COOKIE_NAME = "iroko_token";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Read the auth token from the httpOnly cookie
  const token = request.cookies.get(COOKIE_NAME)?.value;

  // Routes that don't require authentication
  const isLoginRoute          = pathname === "/login" || pathname.startsWith("/login/");
  const isForgotPasswordRoute = pathname.startsWith("/forgot-password");
  const isResetPasswordRoute  = pathname.startsWith("/reset-password");
  const isInviteRoute         = pathname.startsWith("/invite");

  const isPublicAuthRoute = isLoginRoute || isForgotPasswordRoute || isResetPasswordRoute;

  // Authenticated users should not see the login/forgot-password pages
  if (token && isPublicAuthRoute) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Unauthenticated users cannot access protected routes
  if (!token && !isPublicAuthRoute && !isInviteRoute) {
    const loginUrl = new URL("/login", request.url);
    // Pass the attempted path so we can redirect back after login (future enhancement)
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /**
     * Match every path except:
     * - /api/* (Next.js route handlers handle their own auth)
     * - /_next/static, /_next/image (build assets)
     * - favicon.ico, icon.png (static files)
     */
    "/((?!api|_next/static|_next/image|favicon\\.ico|icon\\.png).*)",
  ],
};
