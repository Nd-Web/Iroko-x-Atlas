/**
 * app/api/auth/invitations/route.ts
 *
 * GET — list all invitations.
 *
 * Admin and superadmin only. Used by the Pending Invites page
 * (/user-management/invites) to show all outstanding invite records.
 */

import { apiRequest } from "@/lib/api-client";
import type { InvitationsResponse } from "@/lib/types";

export async function GET() {
  const { data, error, status } = await apiRequest<InvitationsResponse>(
    "/api/auth/invitations"
  );

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return Response.json(data, { status: 200 });
}
