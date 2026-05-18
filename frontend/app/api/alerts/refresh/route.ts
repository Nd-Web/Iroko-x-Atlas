import { apiRequest } from "@/lib/api-client";

export async function POST() {
  const { data, error, status } = await apiRequest("/api/alerts/refresh", {
    method: "POST",
  });

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
