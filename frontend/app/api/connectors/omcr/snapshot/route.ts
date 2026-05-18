import { apiRequest } from "@/lib/api-client";

interface SnapshotWrapper {
  source: string;
  fetched_at: string;
  data: unknown;
}

export async function GET() {
  const { data, error, status } = await apiRequest<SnapshotWrapper>(
    "/api/connectors/omcr/snapshot"
  );
  if (error) return Response.json({ error }, { status: status || 500 });
  // Unwrap the backend envelope — the actual snapshot is nested under `data.data`
  return Response.json(data?.data ?? data, { status: 200 });
}
