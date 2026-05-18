import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const contentType = request.headers.get("content-type") ?? "";

  const fetchOpts = {
    method: "POST",
    headers: {
      "content-type": contentType,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: request.body,
    duplex: "half",
    cache: "no-store",
  } as RequestInit;
  const res = await fetch(`${API_BASE}/api/documents`, fetchOpts);

  const json = await res.json();
  return Response.json(json, { status: res.status });
}
