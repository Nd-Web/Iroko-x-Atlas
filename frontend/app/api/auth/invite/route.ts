/**
 * app/api/auth/invite/route.ts
 *
 * POST — send an invitation email to a new user.
 *
 * Admin and superadmin only. AtlasCore enforces role-based restrictions:
 * - superadmin can invite any role.
 * - admin can only invite analyst/viewer.
 *
 * The invitation email is sent by AtlasCore and contains a one-time link
 * pointing to /invite?token=<token>.
 */

import { apiRequest } from "@/lib/api-client";

interface InvitePayload {
  email: string;
  role: string;
  department: string;
  personal_message?: string;
}

export async function POST(request: Request) {
  let body: InvitePayload;

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { data, error, status } = await apiRequest<string>("/api/auth/invite", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return Response.json({ message: data }, { status: 201 });
}
