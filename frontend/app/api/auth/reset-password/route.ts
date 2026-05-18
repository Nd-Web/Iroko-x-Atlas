/**
 * app/api/auth/reset-password/route.ts
 *
 * POST — submit a new password using the reset token from the email link.
 *
 * The token is read from the URL on the /reset-password page and POSTed here.
 * AtlasCore validates the token expiry and sets the new password.
 */

import { API_BASE } from "@/lib/config";

interface ResetPasswordPayload {
  token: string;
  new_password: string;
}

export async function POST(request: Request) {
  let body: ResetPasswordPayload;

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${API_BASE}/api/auth/reset-password`, {
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

  const data = await backendRes.json();

  if (!backendRes.ok) {
    let errorMsg = "Failed to reset password. The link may have expired.";
    if (data?.detail && typeof data.detail === "string") {
      errorMsg = data.detail;
    }
    return Response.json({ error: errorMsg }, { status: backendRes.status });
  }

  return Response.json(
    { message: "Password reset successfully. You can now sign in." },
    { status: 200 }
  );
}
