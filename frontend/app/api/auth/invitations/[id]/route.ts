/**
 * app/api/auth/invitations/[id]/route.ts
 *
 * DELETE — revoke a pending invitation.
 *
 * Admin and superadmin only. Immediately invalidates the invite link so the
 * recipient can no longer use it to register.
 * Returns 204 No Content on success.
 */

import { apiRequest } from "@/lib/api-client";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const { error, status } = await apiRequest<null>(
    `/api/auth/invitations/${id}`,
    { method: "DELETE" }
  );

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  // 204 from the backend — mirror it
  return new Response(null, { status: 204 });
}
