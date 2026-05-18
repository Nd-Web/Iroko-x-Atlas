import { apiRequest } from "@/lib/api-client";

export async function GET() {
  const { data, error, status } = await apiRequest("/api/connectors");

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}

export async function POST(request: Request) {
  const body = await request.json();
  const { data, error, status } = await apiRequest("/api/connectors", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 201 });
}
