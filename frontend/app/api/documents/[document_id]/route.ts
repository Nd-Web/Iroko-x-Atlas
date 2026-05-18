import { apiRequest } from "@/lib/api-client";
import type { DocumentResponse } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ document_id: string }> }
) {
  const { document_id } = await params;
  const { data, error, status } = await apiRequest<DocumentResponse>(
    `/api/documents/${document_id}`
  );

  if (error) return Response.json({ error }, { status: status || 500 });
  return Response.json(data);
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ document_id: string }> }
) {
  const { document_id } = await params;
  const { error, status } = await apiRequest(
    `/api/documents/${document_id}`,
    { method: "DELETE" }
  );

  if (error) return Response.json({ error }, { status: status || 400 });
  return new Response(null, { status: 204 });
}
