/**
 * lib/proxy.ts
 *
 * Shared server-side helper for Next.js API proxy routes.
 * Forwards a request to the FastAPI backend under the given prefix,
 * reading the httpOnly `iroko_token` cookie and injecting it as a
 * Bearer token (the browser can never read the cookie itself).
 *
 * Used by the thin catch-all routes under app/api/** — same behaviour
 * as the hand-rolled proxies (e.g. app/api/v1/intel/[...path]/route.ts).
 */

import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function proxyToBackend(
  request: NextRequest,
  prefix: string,
  pathSegments: string[] = [],
): Promise<NextResponse> {
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(COOKIE_NAME)?.value;
  const clientAuthHeader = request.headers.get("authorization") ?? "";
  const token = cookieToken ? `Bearer ${cookieToken}` : clientAuthHeader || undefined;

  const subPath = pathSegments.length ? `/${pathSegments.join("/")}` : "";
  const search = request.nextUrl.search ?? "";
  const upstreamUrl = `${API_BASE}${prefix}${subPath}${search}`;

  const forwardHeaders: Record<string, string> = {
    ...(token ? { Authorization: token } : {}),
  };
  const contentType = request.headers.get("content-type");
  if (contentType) forwardHeaders["Content-Type"] = contentType;

  let body: BodyInit | undefined;
  const method = request.method.toUpperCase();
  if (!["GET", "HEAD"].includes(method)) {
    body = await request.text();
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method,
      headers: forwardHeaders,
      body,
      cache: "no-store",
    });
  } catch (err) {
    console.error(`[proxy ${prefix}] upstream fetch failed:`, err);
    return NextResponse.json(
      { error: "Backend unreachable", detail: String(err) },
      { status: 502 },
    );
  }

  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const text = await upstream.text();
  // Live API data must never be cached by the browser/CDN — otherwise a
  // stale empty response survives past the mutation that should refresh it.
  const noStore = { "Cache-Control": "no-store, max-age=0" };
  try {
    return NextResponse.json(JSON.parse(text), { status: upstream.status, headers: noStore });
  } catch {
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "text/plain", ...noStore },
    });
  }
}

type RouteContext = { params: Promise<{ path?: string[] }> };

/** Builds the standard set of method handlers for a catch-all proxy route. */
export function makeProxyHandlers(prefix: string) {
  const handler = async (request: NextRequest, context: RouteContext) => {
    const { path } = await context.params;
    return proxyToBackend(request, prefix, path ?? []);
  };
  return { GET: handler, POST: handler, PUT: handler, PATCH: handler, DELETE: handler };
}
