/**
 * app/api/atlas/export/route.ts
 *
 * POST — Generate a branded PDF or PPTX from an AI answer.
 *
 * Reads the JWT from the httpOnly cookie, forwards the export request to
 * the AtlasCore backend, and streams the binary file response straight
 * through to the browser with the correct Content-Disposition header so
 * the browser triggers a download.
 */

import { cookies } from "next/headers";
import { NextRequest } from "next/server";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  if (!token) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${API_BASE}/api/atlas/export`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    if (!upstream.ok) {
      const text = await upstream.text().catch(() => "Export failed");
      return new Response(text, { status: upstream.status });
    }

    const contentType        = upstream.headers.get("Content-Type") ?? "application/octet-stream";
    const contentDisposition = upstream.headers.get("Content-Disposition") ?? 'attachment; filename="iroko_report"';

    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type":        contentType,
        "Content-Disposition": contentDisposition,
        "Cache-Control":       "no-store",
      },
    });
  } catch {
    return Response.json({ error: "Network error reaching Atlas backend." }, { status: 500 });
  }
}
