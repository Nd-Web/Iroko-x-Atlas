import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const body = await request.text();
    const res = await fetch(`${API_BASE}/api/voice/tts`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "TTS request failed" }));
      const msg = typeof err?.detail === "string" ? err.detail : "TTS request failed";
      return Response.json({ error: msg }, { status: res.status });
    }

    const buf = await res.arrayBuffer();
    return new Response(buf, {
      status: 200,
      headers: { "Content-Type": "audio/mpeg" },
    });
  } catch {
    return Response.json({ error: "Network error reaching Atlas backend." }, { status: 500 });
  }
}
