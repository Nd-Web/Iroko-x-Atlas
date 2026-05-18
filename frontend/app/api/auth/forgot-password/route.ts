/**
 * app/api/auth/forgot-password/route.ts
 *
 * POST — request a password reset link.
 *
 * AtlasCore always returns 200 to prevent email enumeration — i.e. even if
 * the email doesn't exist, the user sees the same success message.
 * The reset email contains a link to /reset-password?token=<token>.
 */

import { API_BASE } from "@/lib/config";

export async function POST(request: Request) {
  let body: { email: string };

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${API_BASE}/api/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: "Network error. Please try again." },
      { status: 503 }
    );
  }

  if (!backendRes.ok) {
    return Response.json(
      { error: "Something went wrong. Please try again." },
      { status: backendRes.status }
    );
  }

  return Response.json(
    { message: "If this email is registered, a reset link has been sent." },
    { status: 200 }
  );
}
