/**
 * app/api/aethex/[...path]/route.ts
 *
 * Server-side proxy for AethexAI API calls.
 * Keeps the secret API key off the browser.
 *
 * Forwards GET / POST / PATCH to https://api.aethexai.com/api/v1/<path>
 * and returns the response (JSON or binary audio).
 */

import { NextRequest, NextResponse } from "next/server";

const AETHEX_BASE  = "https://api.aethexai.com/api/v1";
const AETHEX_KEY   = process.env.AETHEX_API_KEY ?? "";

async function proxy(
  request: NextRequest,
  params: { path: string[] }
): Promise<NextResponse> {
  if (!AETHEX_KEY) {
    return NextResponse.json({ error: "AETHEX_API_KEY not configured" }, { status: 500 });
  }

  const subPath = params.path.join("/");
  const search  = request.nextUrl.search ?? "";
  const url     = `${AETHEX_BASE}/${subPath}${search}`;

  const forwardHeaders: Record<string, string> = {
    "X-API-Key": AETHEX_KEY,
  };

  const contentType = request.headers.get("content-type") ?? "";
  // Forward Content-Type for non-multipart bodies (JSON, etc.).
  // For multipart/form-data we must NOT set Content-Type here — the browser
  // already included the correct boundary in the header, and fetch() will
  // re-attach it automatically when we pass a FormData or raw blob body.
  const isMultipart = contentType.includes("multipart/form-data");
  if (contentType && !isMultipart) {
    forwardHeaders["Content-Type"] = contentType;
  }

  const method = request.method.toUpperCase();
  let body: BodyInit | undefined;
  if (!["GET", "HEAD"].includes(method)) {
    if (isMultipart) {
      // Read as ArrayBuffer to preserve binary integrity of the audio data.
      // Passing the buffer + the original Content-Type (with boundary) lets
      // fetch forward the multipart body byte-for-byte to AethexAI.
      forwardHeaders["Content-Type"] = contentType;
      body = await request.arrayBuffer();
    } else {
      body = await request.text();
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, { method, headers: forwardHeaders, body, cache: "no-store" });
  } catch (err) {
    return NextResponse.json({ error: "AethexAI unreachable", detail: String(err) }, { status: 502 });
  }

  const ct = upstream.headers.get("content-type") ?? "";

  // Audio blobs (WAV / PCM)
  if (ct.includes("audio/")) {
    const buf = await upstream.arrayBuffer();
    return new NextResponse(buf, {
      status: upstream.status,
      headers: { "Content-Type": ct },
    });
  }

  // JSON
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
