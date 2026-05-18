import { apiRequest } from "@/lib/api-client";
import type { DocumentAnalyticsResponse } from "@/lib/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const days = searchParams.get("days");

  const params = new URLSearchParams();
  if (days) params.set("days", days);

  const qs = params.toString();
  const { data, error, status } = await apiRequest<DocumentAnalyticsResponse>(
    `/api/documents/analytics${qs ? `?${qs}` : ""}`
  );

  if (error) return Response.json({ error }, { status: status || 500 });
  return Response.json(data);
}
