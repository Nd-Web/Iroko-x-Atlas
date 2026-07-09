/**
 * components/dashboard/webintel/api.ts
 *
 * API base + fetch helpers for the Web Intelligence dashboard.
 * Auth: reads Bearer token from localStorage["iroko_token"].
 */

export const API = "/api/v1/intel";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("iroko_token") ?? "";
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}
