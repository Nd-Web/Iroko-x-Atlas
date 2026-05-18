/**
 * app/api/auth/accept-invite/route.ts
 *
 * POST — complete registration using an invitation token.
 *
 * After the user fills in their name and password on the /invite page,
 * this handler forwards the data to AtlasCore, which returns a JWT on success.
 * We set the token in an httpOnly cookie so the user is immediately logged in.
 */

import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME, COOKIE_MAX_AGE } from "@/lib/config";
import type { AuthTokenResponse } from "@/lib/types";

interface AcceptInvitePayload {
  token: string;
  full_name: string;
  password: string;
}

export async function POST(request: Request) {
  let body: AcceptInvitePayload;

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${API_BASE}/api/auth/accept-invite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: "Network error. Could not reach the authentication server." },
      { status: 503 }
    );
  }

  const data = await backendRes.json();

  if (!backendRes.ok) {
    let errorMsg = "Could not complete registration. Please try again.";
    if (data?.detail) {
      errorMsg = typeof data.detail === "string" ? data.detail : errorMsg;
    }
    return Response.json({ error: errorMsg }, { status: backendRes.status });
  }

  const { access_token, user } = data as AuthTokenResponse;

  // Log the user in immediately by setting the auth cookie
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
  });

  return Response.json({ user }, { status: 200 });
}
