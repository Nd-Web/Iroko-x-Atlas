/**
 * app/api/compliance-graph/[...path]/route.ts
 *
 * Binary-safe proxy for the compliance knowledge graph API
 * (/api/compliance-graph/*). Same as the returns proxy: the httpOnly
 * session cookie becomes a Bearer token server-side, JSON passes through,
 * and the audit-pack .xlsx streams back with its Content-Disposition intact
 * (lib/proxy.ts reads every response as text, which would corrupt it).
 */

import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

const MAX_REQUEST_BYTES = 1024 * 1024;
const PASS_HEADERS = ["content-type", "content-disposition"];

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: Request, context: RouteContext): Promise<Response> {
  const noStore = { "Cache-Control": "no-store" };
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  if (!token) return Response.json({ detail: "Please sign in." }, { status: 401, headers: noStore });

  const { path } = await context.params;
  const search = new URL(request.url).search;
  const upstreamUrl = `${API_BASE}/api/compliance-graph/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    if (Number(request.headers.get("content-length") ?? 0) > MAX_REQUEST_BYTES) {
      return Response.json({ detail: "The request is too large." }, { status: 413, headers: noStore });
    }
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_REQUEST_BYTES) {
      return Response.json({ detail: "The request is too large." }, { status: 413, headers: noStore });
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
  } catch {
    return Response.json({ detail: "The compliance graph is unreachable. Try again shortly." }, { status: 502, headers: noStore });
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
