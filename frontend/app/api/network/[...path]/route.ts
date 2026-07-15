/**
 * app/api/network/[...path]/route.ts
 *
 * Catch-all proxy: forwards every request under /api/network/*
 * to the FastAPI backend at API_BASE/api/network/*.
 *
 * Handles: GET, POST, PUT, PATCH, DELETE
 * Auth: reads iroko_token cookie and forwards as Bearer token
 */

import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] }
): Promise<NextResponse> {
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(COOKIE_NAME)?.value;
  // Fall back to the Authorization header the client sent (e.g. from localStorage-based auth)
  const clientAuthHeader = request.headers.get("authorization") ?? "";
  const token = cookieToken
    ? `Bearer ${cookieToken}`
    : clientAuthHeader || undefined;

  // Build the upstream URL: /api/network/<rest-of-path>?<query>
  const subPath = params.path.join("/");
  const search = request.nextUrl.search ?? "";
  const upstreamUrl = `${API_BASE}/api/network/${subPath}${search}`;

  // Forward request headers, inject auth
  const forwardHeaders: HeadersInit = {
    ...(token ? { Authorization: token } : {}),
  };

  // Forward Content-Type for requests with a body
  const contentType = request.headers.get("content-type");
  if (contentType) {
    (forwardHeaders as Record<string, string>)["Content-Type"] = contentType;
  }

  // Read body for methods that carry one
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
      // Disable Next.js fetch cache so live signals are always fresh
      cache: "no-store",
    });
  } catch (err) {
    console.error("[network proxy] upstream fetch failed:", err);
    return NextResponse.json(
      { error: "Backend unreachable", detail: String(err) },
      { status: 502 }
    );
  }

  // Standard JSON response
  const text = await upstream.text();
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    // Backend returned non-JSON (e.g. plain error string)
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "text/plain" },
    });
  }

  return NextResponse.json(json, { status: upstream.status });
}

// Export a handler for each HTTP method Next.js supports
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}
