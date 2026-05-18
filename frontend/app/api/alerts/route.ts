import { apiRequest } from "@/lib/api-client";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const status   = searchParams.get("status")   ?? "new";
  const severity = searchParams.get("severity")  ?? "";
  const limit    = searchParams.get("limit")     ?? "50";

  const query = new URLSearchParams({ status, limit });
  if (severity) query.set("severity", severity);

  const { data, error, status: httpStatus } = await apiRequest(
    `/api/alerts?${query.toString()}`
  );

  if (error) {
    return Response.json({ error }, { status: httpStatus || 500 });
  }

  return Response.json(data, { status: 200 });
}
