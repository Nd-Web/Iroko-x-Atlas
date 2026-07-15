/**
 * lib/config.ts
 *
 * Centralised runtime constants for the Iroko AI frontend.
 */

/** Base URL for the Iroko AtlasCore REST API */
export const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "https://iroko-x-atlas.onrender.com"
).replace(/\/+$/, "");

/**
 * Name of the httpOnly cookie that stores the JWT access token.
 */
export const COOKIE_NAME = "iroko_token";

/**
 * Cookie lifetime in seconds — 24 hours.
 *
 * MUST match the backend JWT TTL (ACCESS_TOKEN_EXPIRE_HOURS = 24 in
 * backend/services/auth_utils.py). If the cookie outlives the token, the
 * app looks logged-in while every API call fails with 401 mid-session.
 */
export const COOKIE_MAX_AGE = 60 * 60 * 24;
