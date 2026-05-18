/**
 * lib/api-client.ts
 *
 * Server-side HTTP helper for the AtlasCore backend.
 * Import this ONLY in Route Handlers and Server Components — never in
 * "use client" files.  It reads the httpOnly JWT cookie via next/headers,
 * which is only available in a server context.
 */

import { cookies } from "next/headers";
import { API_BASE, COOKIE_NAME } from "./config";

/** Shape returned by every apiRequest call */
export interface ApiResult<T> {
  data: T | null;
  error: string | null;
  status: number;
}

/** Options forwarded to fetch(), minus the `headers` key (we manage that) */
type RequestOptions = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
  /** Pass a raw token string to skip reading from the cookie store */
  bearerToken?: string;
};

/**
 * Make an authenticated HTTP request to the AtlasCore backend.
 *
 * - Reads the JWT from the iroko_token httpOnly cookie (or an explicit token).
 * - Parses FastAPI-style validation errors into a single human-readable string.
 * - Returns a discriminated union so callers can handle success and error
 *   paths without throwing.
 */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<ApiResult<T>> {
  // Read the token from the cookie store unless one is passed explicitly
  const cookieStore = await cookies();
  const token = options.bearerToken ?? cookieStore.get(COOKIE_NAME)?.value;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      // Auth responses must never be served from cache
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });

    // 204 No Content — treat as success with no body
    if (res.status === 204) {
      return { data: null, error: null, status: 204 };
    }

    const json = await res.json();

    if (!res.ok) {
      // FastAPI returns errors in two shapes:
      //   { detail: "string message" }
      //   { detail: [{ loc: [...], msg: "string", type: "string" }] }
      let errorMsg = "Something went wrong. Please try again.";
      if (json?.detail) {
        if (typeof json.detail === "string") {
          errorMsg = json.detail;
        } else if (Array.isArray(json.detail) && json.detail[0]?.msg) {
          errorMsg = json.detail[0].msg;
        }
      }
      return { data: null, error: errorMsg, status: res.status };
    }

    return { data: json as T, error: null, status: res.status };
  } catch {
    // Network failure or JSON parse error
    return {
      data: null,
      error: "Network error. Please check your connection and try again.",
      status: 0,
    };
  }
}
