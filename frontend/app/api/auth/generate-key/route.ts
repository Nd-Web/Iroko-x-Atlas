/**
 * app/api/auth/generate-key/route.ts
 *
 * POST — rotate the API key for the currently authenticated user.
 *
 * Returns the new API key string. This is displayed once in the Profile
 * settings page — the user must copy it immediately.
 */

import { apiRequest } from "@/lib/api-client";

export async function POST() {
  const { data, error, status } = await apiRequest<string>(
    "/api/auth/generate-key",
    { method: "POST" }
  );

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return Response.json({ key: data }, { status: 200 });
}
