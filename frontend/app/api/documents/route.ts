import { apiRequest } from "@/lib/api-client";
import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "@/lib/config";
import type { DocumentListResponse, DocumentResponse } from "@/lib/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();

  const department = searchParams.get("department");
  const doc_type = searchParams.get("doc_type");
  const status = searchParams.get("status");
  const page = searchParams.get("page") ?? "1";
  const page_size = searchParams.get("page_size") ?? "20";

  if (department) params.set("department", department);
  if (doc_type) params.set("doc_type", doc_type);
  if (status) params.set("status", status);
  params.set("page", page);
  params.set("page_size", page_size);

  const { data, error, status: httpStatus } = await apiRequest<DocumentListResponse>(
    `/api/documents?${params.toString()}`
  );

  if (error) return Response.json({ error }, { status: httpStatus || 500 });
  return Response.json(data);
}

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const contentType = request.headers.get("content-type") ?? "";

  // Stream body directly to FastAPI — avoids buffering the full file into memory
  // and bypasses Next.js's 10 MB formData parsing limit.
  const fetchOpts = {
    method: "POST",
    headers: {
      "content-type": contentType,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: request.body,
    duplex: "half", // required by Node.js when body is a ReadableStream
    cache: "no-store",
  } as RequestInit;
  const res = await fetch(`${API_BASE}/api/documents`, fetchOpts);

  const json = await res.json();
  return Response.json(json, { status: res.status });
}
