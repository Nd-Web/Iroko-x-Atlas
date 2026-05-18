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
import { API_BASE, COOKIE_NAME, COOKIE_MAX_AGE } from "@/lib/config";
import type { AuthTokenResponse } from "@/lib/types";

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

  // Forward to AtlasCore
  let backendRes: Response;
  try {
    backendRes = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    return Response.json(
      { error: "Network error. Could not reach the authentication server." },
      { status: 503 }
    );
  }

  const contentType = backendRes.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return Response.json(
      { error: "Backend unavailable. Please try again." },
      { status: 503 }
    );
  }
  const data = await backendRes.json();

  if (!backendRes.ok) {
    // Surface a human-readable error message from FastAPI
    let errorMsg = "Login failed. Please check your credentials.";
    if (data?.detail) {
      errorMsg = typeof data.detail === "string" ? data.detail : errorMsg;
    }
    return Response.json({ error: errorMsg }, { status: backendRes.status });
  }

  const { access_token, user } = data as AuthTokenResponse;

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
  return Response.json({ user }, { status: 200 });
}
