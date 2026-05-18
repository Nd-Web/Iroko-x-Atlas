/**
 * components/ui/LoadingSpinner.tsx
 *
 * A small animated SVG spinner for use inside buttons and page-level loaders.
 * Accepts size and color props so it works on both light and dark backgrounds.
 */

"use client";

interface LoadingSpinnerProps {
  /** Pixel dimensions for width and height (default: 16) */
  size?: number;
}

export default function LoadingSpinner({ size = 16 }: LoadingSpinnerProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className="animate-spin"
      aria-label="Loading"
    >
      {/* Faded track */}
      <circle
        cx="8"
        cy="8"
        r="6"
        stroke="currentColor"
        strokeWidth="2"
        opacity="0.25"
      />
      {/* Spinning arc */}
      <path
        d="M8 2a6 6 0 0 1 6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
