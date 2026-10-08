/**
 * app/api/returns/[...path]/route.ts
 *
 * Binary-safe proxy for the regulatory returns API. Unlike lib/proxy.ts
 * (JSON only), this passes multipart uploads through untouched and streams
 * .docx/.xlsx/.zip downloads back with their Content-Disposition intact.
 */

import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

// 10 MB workbook limit on the backend, plus multipart overhead.
const MAX_REQUEST_BYTES = 11 * 1024 * 1024;
const PASS_HEADERS = ["content-type", "content-disposition"];

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: Request, context: RouteContext): Promise<Response> {
  const noStore = { "Cache-Control": "no-store" };
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  if (!token) return Response.json({ detail: "Please sign in." }, { status: 401, headers: noStore });

  const { path } = await context.params;
  const search = new URL(request.url).search;
  const upstreamUrl = `${API_BASE}/api/returns/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    if (Number(request.headers.get("content-length") ?? 0) > MAX_REQUEST_BYTES) {
      return Response.json({ detail: "The upload exceeds the 10 MB limit." }, { status: 413, headers: noStore });
    }
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_REQUEST_BYTES) {
      return Response.json({ detail: "The upload exceeds the 10 MB limit." }, { status: 413, headers: noStore });
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
  } catch {
    return Response.json({ detail: "The returns service is unreachable. Try again shortly." }, { status: 502, headers: noStore });
  }

  const out = new Headers(noStore);
  for (const h of PASS_HEADERS) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
