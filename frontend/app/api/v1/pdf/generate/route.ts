/**
 * app/api/v1/pdf/generate/route.ts
 *
 * Proxies PDF generation requests to the FastAPI backend.
 * This allows the frontend to call /api/v1/pdf/generate (relative URL)
 * instead of hardcoding http://localhost:8000, and ensures the auth
 * cookie is forwarded as a Bearer token.
 */

import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const forwardHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/api/v1/pdf/generate`, {
      method: "POST",
      headers: forwardHeaders,
      body: await request.text(),
      cache: "no-store",
    });
  } catch (err) {
    console.error("[pdf proxy] upstream fetch failed:", err);
    return NextResponse.json(
      { error: "Backend unreachable", detail: String(err) },
      { status: 502 }
    );
  }

  if (!upstream.ok) {
    const text = await upstream.text().catch(() => "");
    return NextResponse.json(
      { error: "PDF generation failed", detail: text },
      { status: upstream.status }
    );
  }

  // Stream the PDF binary back with correct headers
  const pdfBuffer = await upstream.arrayBuffer();
  return new NextResponse(pdfBuffer, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": 'attachment; filename="iroko-ai-detailed-report.pdf"',
    },
  });
}
