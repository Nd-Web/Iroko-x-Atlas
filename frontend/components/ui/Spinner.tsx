"use client";
/**
 * components/ui/Spinner.tsx
 * The single loading spinner for the app. Inherits `currentColor` so it
 * adapts to any context (buttons, page loaders, light or dark surfaces).
 * Accepts a named size ("sm" | "md" | "lg") or an exact pixel number.
 */
import React from "react";
import { cn } from "@/lib/utils";

type NamedSize = "sm" | "md" | "lg";
type NamedColor = "white" | "blue" | "amber";

const NAMED_SIZES: Record<NamedSize, number> = { sm: 16, md: 24, lg: 40 };
const NAMED_COLORS: Record<NamedColor, string> = {
  white: "text-white",
  blue: "text-info-500",
  amber: "text-warning-500",
};

interface SpinnerProps {
  size?: number | NamedSize;
  /** Optional named color; omit to inherit currentColor from the parent. */
  color?: NamedColor;
  className?: string;
}

export default function Spinner({ size = "md", color, className }: SpinnerProps) {
  const px = typeof size === "number" ? size : NAMED_SIZES[size];
  return (
    <svg
      width={px}
      height={px}
      viewBox="0 0 16 16"
      fill="none"
      className={cn("animate-spin shrink-0", color && NAMED_COLORS[color], className)}
      role="status"
      aria-label="Loading"
    >
      {/* Faded track */}
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" opacity="0.25" />
      {/* Spinning arc */}
      <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
