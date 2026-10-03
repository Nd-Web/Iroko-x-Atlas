/**
 * app/api/auth/login/route.ts
 *
 * Proxy route for POST /api/auth/login.
 *
 * Flow:
 * 1. Client POSTs { email, password } to this handler.
 * 2. We forward the credentials to AtlasCore.
 * 3. On success, we store the returned JWT in an httpOnly cookie and return
 *    the user object to the client.
 * 4. On failure, we forward the error message back to the client.
 *
 * The cookie is httpOnly so it cannot be read by JavaScript — this protects
 * against XSS-based token theft.
 */

import { cookies } from "next/headers";
import { COOKIE_NAME, COOKIE_MAX_AGE } from "@/lib/config";
import { loginToBackend } from "@/lib/auth-login-proxy";

export const maxDuration = 30;

export async function POST(request: Request) {
  let body: unknown;

  // Parse the incoming JSON body
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "Invalid request body." },
      { status: 400 }
    );
  }

  const result = await loginToBackend(body);
  if (!result.ok) {
    return Response.json({ error: result.error }, { status: result.status,
      headers: { "Cache-Control": "private, no-store", ...(result.status >= 500 ? { "Retry-After": "5" } : {}) } });
  }

  const { access_token, user } = result.data;

  // Set the JWT as an httpOnly cookie so it is never accessible from JS
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
  });

  // Only return safe user data to the client — never the raw token
  return Response.json({ user }, { status: 200, headers: { "Cache-Control": "private, no-store" } });
}
