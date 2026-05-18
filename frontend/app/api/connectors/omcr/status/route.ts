import { apiRequest } from "@/lib/api-client";

export async function GET() {
  const { data, error, status } = await apiRequest("/api/connectors/omcr/status");
  if (error) return Response.json({ error }, { status: status || 500 });
  return Response.json(data, { status: 200 });
}
