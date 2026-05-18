/**
 * app/api/auth/me/route.ts
 *
 * GET  — return the currently authenticated user's profile.
 * PATCH — update own profile (full_name, department).
 *         Role changes require superadmin and are handled server-side by AtlasCore.
 *
 * Both methods read the JWT from the httpOnly cookie and forward the request to
 * the AtlasCore backend.
 */

import { apiRequest } from "@/lib/api-client";
import type { User, UpdateMePayload } from "@/lib/types";

/** GET /api/auth/me → returns the current user object */
export async function GET() {
  const { data, error, status } = await apiRequest<User>("/api/auth/me");

  if (error) {
    return Response.json({ error }, { status: status || 401 });
  }

  return Response.json(data, { status: 200 });
}

/** PATCH /api/auth/me → update own profile */
export async function PATCH(request: Request) {
  let body: UpdateMePayload;

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { data, error, status } = await apiRequest<User>("/api/auth/me", {
    method: "PATCH",
    body: JSON.stringify(body),
  });

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return Response.json(data, { status: 200 });
}
