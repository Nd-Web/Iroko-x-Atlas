/**
 * lib/auth.ts
 *
 * Cookie-based JWT auth utilities for Iroko AI frontend.
 * Works in both browser and SSR contexts (reads document.cookie in browser).
 */

const COOKIE_NAME = "auth_token";
const COOKIE_EXPIRY_DAYS = 7;

/** Parse a single cookie value from a cookie string. */
function parseCookie(cookieStr: string, name: string): string | null {
  const pairs = cookieStr.split(";");
  for (const pair of pairs) {
    const [key, ...rest] = pair.trim().split("=");
    if (key.trim() === name) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return null;
}

/**
 * Read the JWT auth token from the ``auth_token`` cookie.
 * Returns ``null`` if not set or running on the server.
 */
export function getAuthToken(): string | null {
  if (typeof document === "undefined") return null;

  // Prefer js-cookie if it's been bundled, fall back to manual parsing
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Cookies = require("js-cookie");
    return Cookies.get(COOKIE_NAME) ?? null;
  } catch {
    return parseCookie(document.cookie, COOKIE_NAME);
  }
}

/**
 * Persist the JWT in a browser cookie with a 7-day expiry.
 * SameSite=Strict prevents CSRF. Secure flag is set in production.
 */
export function setAuthToken(token: string): void {
  if (typeof document === "undefined") return;

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Cookies = require("js-cookie");
    Cookies.set(COOKIE_NAME, token, {
      expires: COOKIE_EXPIRY_DAYS,
      sameSite: "strict",
      secure: window.location.protocol === "https:",
    });
    return;
  } catch {
    // Fallback to manual cookie setting
    const expires = new Date();
    expires.setDate(expires.getDate() + COOKIE_EXPIRY_DAYS);
    const secure = window.location.protocol === "https:" ? ";Secure" : "";
    document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)};expires=${expires.toUTCString()};path=/;SameSite=Strict${secure}`;
  }
}

/**
 * Delete the ``auth_token`` cookie (logout).
 */
export function removeAuthToken(): void {
  if (typeof document === "undefined") return;

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Cookies = require("js-cookie");
    Cookies.remove(COOKIE_NAME, { path: "/" });
    return;
  } catch {
    // Expire the cookie immediately
    document.cookie = `${COOKIE_NAME}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;SameSite=Strict`;
  }
}

/**
 * Returns ``true`` if a non-empty auth token cookie exists.
 * Does NOT validate the JWT signature — use server-side validation for that.
 */
export function isAuthenticated(): boolean {
  const token = getAuthToken();
  return token !== null && token.length > 0;
}
