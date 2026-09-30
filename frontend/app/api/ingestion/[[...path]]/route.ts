import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

async function handler(request: Request, context: { params: Promise<{ path?: string[] }> }) {
  const { path = [] } = await context.params;
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  if (!token) return Response.json({ error: "Sign in to continue" }, { status: 401 });
  try {
    const upstream = await fetch(`${API_BASE}/api/ingestion/${path.map(encodeURIComponent).join("/")}${new URL(request.url).search}`, {
      method: request.method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(60000),
    });
    return new Response(upstream.body, { status: upstream.status, headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "private, no-store",
      ...(upstream.headers.get("content-disposition") ? { "Content-Disposition": upstream.headers.get("content-disposition")! } : {}),
    } });
  } catch {
    return Response.json({ error: "Document service is temporarily unavailable" }, { status: 502 });
  }
}

export { handler as GET, handler as POST, handler as PATCH };
