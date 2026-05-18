import { apiRequest } from "@/lib/api-client";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ connector_id: string }> }
) {
  const { connector_id } = await params;
  const body = await request.json();
  const { data, error, status } = await apiRequest(
    `/api/connectors/${connector_id}/import`,
    { method: "POST", body: JSON.stringify(body) }
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
