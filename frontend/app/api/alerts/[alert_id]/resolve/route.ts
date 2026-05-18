import { apiRequest } from "@/lib/api-client";

export async function PATCH(
  _request: Request,
  { params }: { params: Promise<{ alert_id: string }> }
) {
  const { alert_id } = await params;

  const { data, error, status } = await apiRequest(
    `/api/alerts/${alert_id}/resolve`,
    { method: "PATCH" }
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
