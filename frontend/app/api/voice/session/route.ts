import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const body = await request.text();
    const res = await fetch(`${API_BASE}/api/voice/session`, {
      method: "POST",
      headers,
      body: body || "{}",
      cache: "no-store",
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = typeof data?.detail === "string" ? data.detail : "Session create failed";
      return Response.json({ error: msg }, { status: res.status });
    }
    return Response.json(data, { status: 200 });
  } catch {
    return Response.json({ error: "Network error reaching Atlas backend." }, { status: 500 });
  }
}
