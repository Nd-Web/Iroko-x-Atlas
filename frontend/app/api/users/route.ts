import { apiRequest } from "@/lib/api-client";
import type { UserListResponse } from "@/lib/types";

export async function GET() {
  const { data, error, status } = await apiRequest<UserListResponse>("/api/users");

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
