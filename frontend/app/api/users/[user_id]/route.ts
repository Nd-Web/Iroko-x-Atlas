import { apiRequest } from "@/lib/api-client";
import type { User, UpdateUserRequest } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ user_id: string }> }
) {
  const { user_id } = await params;
  const { data, error, status } = await apiRequest<User>(`/api/users/${user_id}`);

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ user_id: string }> }
) {
  const { user_id } = await params;

  let body: UpdateUserRequest;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { data, error, status } = await apiRequest<User>(`/api/users/${user_id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return Response.json(data, { status: 200 });
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ user_id: string }> }
) {
  const { user_id } = await params;
  const { error, status } = await apiRequest<null>(`/api/users/${user_id}`, {
    method: "DELETE",
  });

  if (error) {
    return Response.json({ error }, { status: status || 400 });
  }

  return new Response(null, { status: 204 });
}
