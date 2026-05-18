import { apiRequest } from "@/lib/api-client";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") ?? "50";

  const query = new URLSearchParams({ limit });
  const { data, error, status } = await apiRequest(
    `/api/analytics/knowledge-gaps?${query.toString()}`
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
