import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

// Includes a small allowance for multipart field/header overhead.
const MAX_REQUEST_BYTES = 51 * 1024 * 1024;

export function proxyDocumentUpload(request: Request) {
  return proxyMultipartUpload(request, "/api/documents");
}

/** Stream an authenticated multipart body to a backend upload endpoint. */
export async function proxyMultipartUpload(request: Request, backendPath: string) {
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  const responseHeaders = { "Cache-Control": "private, no-store" };
  const error = (detail: string, status: number) =>
    Response.json({ detail, error: detail }, { status, headers: responseHeaders });
  if (!token) return error("Please sign in to upload documents.", 401);
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().startsWith("multipart/form-data;") || !request.body) {
    return error("A multipart document upload is required.", 400);
  }
  const length = Number(request.headers.get("content-length") ?? 0);
  if (!Number.isFinite(length) || length < 0 || length > MAX_REQUEST_BYTES) {
    return error("Upload exceeds the 50 MB document limit.", 413);
  }
  let received = 0;
  let tooLarge = false;
  const body = request.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      received += chunk.byteLength;
      if (received > MAX_REQUEST_BYTES) {
        tooLarge = true;
        controller.error(new Error("Upload limit exceeded"));
        return;
      }
      controller.enqueue(chunk);
    },
  }));
  const options: RequestInit & { duplex: "half" } = {
    method: "POST", headers: { "content-type": contentType, Authorization: `Bearer ${token}` },
    body, duplex: "half", cache: "no-store",
    signal: AbortSignal.any([request.signal, AbortSignal.timeout(120_000)]),
  };
  try {
    const upstream = await fetch(`${API_BASE}${backendPath}`, options);
    if (!upstream.headers.get("content-type")?.includes("application/json")) {
      return error("Upload service is temporarily unavailable. Check your document list before retrying.", 502);
    }
    const data = await upstream.json();
    const retryAfter = upstream.headers.get("retry-after");
    return Response.json(data, { status: upstream.status, headers: {
      ...responseHeaders, ...(retryAfter ? { "Retry-After": retryAfter } : {}),
    } });
  } catch {
    if (tooLarge) return error("Upload exceeds the 50 MB document limit.", 413);
    return error("Upload connection interrupted. Check your document list before retrying the same file.", 503);
  }
}
