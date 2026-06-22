/**
 * app/api/agent/[...path]/route.ts
 *
 * Server-side proxy for the Iroko AI voice agent API calls.
 * Keeps the API key off the browser.
 */

import { NextRequest, NextResponse } from "next/server";

const AGENT_BASE = "https://api.aethexai.com/api/v1";

const API_KEY = process.env.IROKO_AGENT_API_KEY ?? "";

async function callUpstream(
  url: string,
  method: string,
  headers: Record<string, string>,
  body: BodyInit | undefined,
): Promise<Response> {
  return fetch(url, {
    method,
    headers: { ...headers, "X-API-Key": API_KEY },
    body,
    cache: "no-store",
  });
}

async function proxy(
  request: NextRequest,
  params: { path: string[] }
): Promise<NextResponse> {
  if (!API_KEY) {
    return NextResponse.json({ error: "IROKO_AGENT_API_KEY not configured" }, { status: 500 });
  }

  const subPath = params.path.join("/");
  const search  = request.nextUrl.search ?? "";
  const url     = `${AGENT_BASE}/${subPath}${search}`;

  const contentType = request.headers.get("content-type") ?? "";
  const isMultipart = contentType.includes("multipart/form-data");

  const forwardHeaders: Record<string, string> = {};
  if (contentType && !isMultipart) {
    forwardHeaders["Content-Type"] = contentType;
  }

  const method = request.method.toUpperCase();
  let body: BodyInit | undefined;
  if (!["GET", "HEAD"].includes(method)) {
    if (isMultipart) {
      forwardHeaders["Content-Type"] = contentType;
      body = await request.arrayBuffer();
    } else {
      body = await request.text();
    }
  }

  let upstream: Response;
  try {
    upstream = await callUpstream(url, method, forwardHeaders, body);
  } catch (err) {
    return NextResponse.json({ error: "Agent API unreachable", detail: String(err) }, { status: 502 });
  }

  const ct = upstream.headers.get("content-type") ?? "";

  if (ct.includes("audio/")) {
    const buf = await upstream.arrayBuffer();
    return new NextResponse(buf, {
      status: upstream.status,
      headers: { "Content-Type": ct },
    });
  }

  const text = await upstream.text();
  try {
    const json = JSON.parse(text);
    return NextResponse.json(json, { status: upstream.status });
  } catch {
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "text/plain" },
    });
  }
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}
