/**
 * app/api/auth/invite/[token]/route.ts
 *
 * GET — validate an invitation token.
 *
 * Called by the /invite page on mount before displaying the sign-up form.
 * Returns the associated email, role, department, and invited_by so the
 * form can be pre-filled and the user cannot change their own email.
 *
 * This route does NOT require authentication — anyone arriving via an
 * invite link can call it.
 */

import { API_BASE } from "@/lib/config";
import type { InviteTokenPayload } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params;

  let backendRes: Response;
  try {
    backendRes = await fetch(`${API_BASE}/api/auth/invite/${token}`, {
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: "Network error. Could not validate the invite token." },
      { status: 503 }
    );
  }

  const data = await backendRes.json();

  if (!backendRes.ok) {
    const errorMsg =
      typeof data?.detail === "string"
        ? data.detail
        : "This invitation link is invalid or has expired.";
    return Response.json({ error: errorMsg }, { status: backendRes.status });
  }

  return Response.json(data as InviteTokenPayload, { status: 200 });
}
