import { apiRequest } from "@/lib/api-client";
import type { User } from "@/lib/types";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ user_id: string }> }
) {
  const { user_id } = await params;
  const { data, error, status } = await apiRequest<User>(
    `/api/users/${user_id}/deactivate`,
    { method: "POST" }
  );

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return Response.json(data, { status: 200 });
}
