import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const { searchParams } = new URL(request.url);
  const conversationId = searchParams.get("conversation_id");

  const backendUrl = `${API_BASE}/api/atlas/voice${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""}`;

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Do NOT set Content-Type — fetch sets it automatically with the multipart boundary

  try {
    const formData = await request.formData();
    const res = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: formData,
      cache: "no-store",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Voice request failed" }));
      const msg =
        typeof err?.detail === "string"
          ? err.detail
          : Array.isArray(err?.detail) && err.detail[0]?.msg
          ? err.detail[0].msg
          : "Voice request failed";
      return Response.json({ error: msg }, { status: res.status });
    }

    const data = await res.json();
    return Response.json(data, { status: 200 });
  } catch {
    return Response.json(
      { error: "Network error reaching Atlas backend." },
      { status: 500 }
    );
  }
}
