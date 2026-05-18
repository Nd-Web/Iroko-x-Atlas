import { apiRequest } from "@/lib/api-client";

export async function GET(
  _: Request,
  { params }: { params: Promise<{ connector_id: string }> }
) {
  const { connector_id } = await params;
  const { data, error, status } = await apiRequest(`/api/connectors/${connector_id}`);

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ connector_id: string }> }
) {
  const { connector_id } = await params;
  const body = await request.json();
  const { data, error, status } = await apiRequest(`/api/connectors/${connector_id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}

export async function DELETE(
  _: Request,
  { params }: { params: Promise<{ connector_id: string }> }
) {
  const { connector_id } = await params;
  const { data, error, status } = await apiRequest(`/api/connectors/${connector_id}`, {
    method: "DELETE",
  });

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
