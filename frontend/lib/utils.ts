/**
 * lib/utils.ts
 *
 * Shared utility functions for Iroko AI frontend.
 */

// ── Class merging ─────────────────────────────────────────────────────────────

/**
 * Merge Tailwind class strings, filtering out falsy values.
 * Drop-in replacement for clsx/classnames — no external dep needed.
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(" ");
}

// ── Date formatting ───────────────────────────────────────────────────────────

/**
 * Format a date as "May 14, 2026".
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "Invalid date";
  return d.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Return a human-readable relative time string such as "2 hours ago",
 * "just now", or "3 days ago".
 */
export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "unknown";

  const ms = Date.now() - d.getTime();
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return formatDate(d);
}

// ── String utilities ──────────────────────────────────────────────────────────

/**
 * Truncate a string to ``maxLength`` characters, appending "…" if clipped.
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 1) + "…";
}

// ── Risk scoring ──────────────────────────────────────────────────────────────

/**
 * Return a Tailwind text-colour class based on a 0–10 risk score.
 *
 * - ≤ 3  → green   (text-emerald-400)
 * - 4–6  → amber   (text-amber-400)
 * - ≥ 7  → red     (text-red-400)
 */
export function getRiskColor(score: number): string {
  if (score <= 3) return "text-emerald-400";
  if (score <= 6) return "text-amber-400";
  return "text-red-400";
}

/**
 * Return a human-readable risk label for a 0–10 score.
 */
export function getRiskLabel(score: number): "Low" | "Medium" | "High" {
  if (score <= 3) return "Low";
  if (score <= 6) return "Medium";
  return "High";
}

/**
 * Return a hex colour string for a risk score (for inline styles).
 */
export function getRiskHex(score: number): string {
  if (score <= 3) return "#10B981";
  if (score <= 6) return "#F59E0B";
  return "#EF4444";
}

// ── Number formatting ─────────────────────────────────────────────────────────

/** Format a number with commas, e.g. 1234567 → "1,234,567". */
export function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

/** Format milliseconds as "1.4s" or "340ms". */
export function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

/**
 * Format a byte count as a human-readable string.
 * e.g. 1024 → "1 KB", 1536000 → "1.5 MB"
 */
export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const value = bytes / Math.pow(k, i);
  return `${value % 1 === 0 ? value : value.toFixed(decimals)} ${sizes[i]}`;
}

