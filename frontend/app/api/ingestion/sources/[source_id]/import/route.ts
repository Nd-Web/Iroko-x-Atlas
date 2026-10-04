import { proxyMultipartUpload } from "@/lib/document-upload-proxy";

// Multipart import of a regulator file downloaded from its official link.
// The catch-all ingestion proxy forwards JSON only.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ source_id: string }> }
) {
  const { source_id } = await params;
  return proxyMultipartUpload(request, `/api/ingestion/sources/${encodeURIComponent(source_id)}/import`);
}
