import { apiRequest } from "@/lib/api-client";
import type { DocumentListResponse } from "@/lib/types";
export { proxyDocumentUpload as POST } from "@/lib/document-upload-proxy";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();

  const department = searchParams.get("department");
  const doc_type = searchParams.get("doc_type");
  const status = searchParams.get("status");
  const page = searchParams.get("page") ?? "1";
  const page_size = searchParams.get("page_size") ?? "20";

  if (department) params.set("department", department);
  if (doc_type) params.set("doc_type", doc_type);
  if (status) params.set("status", status);
  params.set("page", page);
  params.set("page_size", page_size);

  const { data, error, status: httpStatus } = await apiRequest<DocumentListResponse>(
    `/api/documents?${params.toString()}`
  );

  if (error) return Response.json({ error }, { status: httpStatus || 500 });
  return Response.json(data);
}
