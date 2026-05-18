import { apiRequest } from "@/lib/api-client";
import type { DocumentSearchResponse } from "@/lib/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);

  const q = searchParams.get("q");
  if (!q) return Response.json({ error: "q is required" }, { status: 400 });

  const params = new URLSearchParams({ q });

  const top = searchParams.get("top");
  const department = searchParams.get("department");
  const doc_type = searchParams.get("doc_type");
  const language = searchParams.get("language");
  const classification = searchParams.get("classification");
  const rerank = searchParams.get("rerank");

  if (top) params.set("top", top);
  if (department) params.set("department", department);
  if (doc_type) params.set("doc_type", doc_type);
  if (language) params.set("language", language);
  if (classification) params.set("classification", classification);
  if (rerank !== null) params.set("rerank", rerank ?? "true");

  const { data, error, status } = await apiRequest<DocumentSearchResponse>(
    `/api/documents/search?${params.toString()}`
  );

  if (error) return Response.json({ error }, { status: status || 500 });
  return Response.json(data);
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { data, error, status } = await apiRequest<DocumentSearchResponse>(
    `/api/documents/search`,
    { method: "POST", body: JSON.stringify(body) }
  );

  if (error) return Response.json({ error }, { status: status || 500 });
  return Response.json(data);
}
