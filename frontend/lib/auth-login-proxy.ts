/** Server-only login transport: bounded retries for transient gateway failures. */
import { API_BASE } from "@/lib/config";
import type { AuthTokenResponse } from "@/lib/types";

type LoginResult =
  | { ok: true; data: AuthTokenResponse }
  | { ok: false; status: number; error: string };

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function authResponse(value: unknown): value is AuthTokenResponse {
  return record(value) && typeof value.access_token === "string" &&
    value.access_token.length > 0 && record(value.user) &&
    typeof value.user.id === "string" && typeof value.user.email === "string" &&
    typeof value.user.role === "string";
}

export async function loginToBackend(body: unknown): Promise<LoginResult> {
  if (!record(body) || typeof body.email !== "string" || !body.email.trim() ||
      typeof body.password !== "string" || !body.password) {
    return { ok: false, status: 400, error: "Enter your email and password." };
  }
  const serialized = JSON.stringify({ email: body.email.trim(), password: body.password });
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: serialized, cache: "no-store", redirect: "error",
        signal: AbortSignal.timeout(10000),
      });
      // Render gateway/wakeup responses may be HTML; never expose them as auth errors.
      if ([502, 503, 504].includes(response.status) && attempt === 0) {
        await response.body?.cancel();
        continue;
      }
      if (response.status >= 500) {
        return { ok: false, status: 503, error: "Authentication service is temporarily unavailable. Please try again shortly." };
      }
      let data: unknown;
      try {
        data = await response.json();
      } catch {
        return { ok: false, status: 502, error: "Authentication service returned an invalid response. Please try again shortly." };
      }
      if (!response.ok) {
        const fallback = response.status === 422 ? "Check your email and password fields." : "Login failed. Please check your credentials.";
        return { ok: false, status: response.status,
          error: record(data) && typeof data.detail === "string" ? data.detail : fallback };
      }
      if (!authResponse(data)) {
        return { ok: false, status: 502, error: "Authentication service returned an invalid response. Please try again shortly." };
      }
      return { ok: true, data };
    } catch {
      if (attempt === 0) continue;
    }
  }
  return { ok: false, status: 503, error: "Authentication service is taking longer to respond. Please try again shortly." };
}
