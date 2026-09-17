import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Do NOT set Content-Type — fetch sets it automatically with the multipart boundary

  try {
    const formData = await request.formData();
    const res = await fetch(`${API_BASE}/api/voice/transcribe`, {
      method: "POST",
      headers,
      body: formData,
      cache: "no-store",
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = typeof data?.detail === "string" ? data.detail : "Transcription failed";
      return Response.json({ error: msg }, { status: res.status });
    }
    return Response.json(data, { status: 200 });
  } catch {
    return Response.json({ error: "Network error reaching Atlas backend." }, { status: 500 });
  }
}
