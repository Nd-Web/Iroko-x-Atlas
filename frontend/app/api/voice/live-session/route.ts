/**
 * GPT-Live WebRTC session for the voice agent. The browser sends its SDP offer;
 * the backend creates the session with the Azure key (never sent to the browser)
 * and returns Azure's SDP answer.
 */
import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  if (!token) return Response.json({ error: "Sign in to talk to the compliance agent." }, { status: 401 });

  try {
    const res = await fetch(`${API_BASE}/api/voice/live-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: await request.text(),
      cache: "no-store",
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = typeof data?.detail === "string" ? data.detail : `Voice session failed (${res.status})`;
      return Response.json({ error: msg }, { status: res.status });
    }
    return Response.json(data, { status: 200 });
  } catch {
    return Response.json({ error: "Network error reaching Atlas backend." }, { status: 502 });
  }
}
