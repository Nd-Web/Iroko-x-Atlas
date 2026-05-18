/**
 * lib/config.ts
 *
 * Centralised runtime constants for the Iroko AI frontend.
 */

/** Base URL for the Iroko AtlasCore REST API */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Name of the httpOnly cookie that stores the JWT access token.
 */
export const COOKIE_NAME = "iroko_token";

/**
 * Cookie lifetime in seconds — 7 days.
 */
export const COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
