/**
 * Backs the voice agent's check_compliance tool. The browser holds the WebRTC
 * data channel, so it executes the tool call — this forwards it to the real
 * compliance engine with the caller's session cookie.
 */
import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const body = await request.text();
    const res = await fetch(`${API_BASE}/api/v1/compliance/check`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = typeof data?.detail === "string" ? data.detail : "Compliance check failed";
      return Response.json({ error: msg }, { status: res.status });
    }
    return Response.json(data, { status: 200 });
  } catch {
    return Response.json({ error: "Network error reaching Atlas backend." }, { status: 500 });
  }
}
