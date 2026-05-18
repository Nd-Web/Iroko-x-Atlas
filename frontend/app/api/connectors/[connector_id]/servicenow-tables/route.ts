import { apiRequest } from "@/lib/api-client";

export async function GET(
  _: Request,
  { params }: { params: Promise<{ connector_id: string }> }
) {
  const { connector_id } = await params;
  const { data, error, status } = await apiRequest(
    `/api/connectors/${connector_id}/servicenow-tables`
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
