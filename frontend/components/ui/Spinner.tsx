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

const NAMED_SIZES: Record<NamedSize, number> = { sm: 16, md: 24, lg: 40 };

interface SpinnerProps {
  size?: number | NamedSize;
  className?: string;
}

export default function Spinner({ size = "md", className }: SpinnerProps) {
  const px = typeof size === "number" ? size : NAMED_SIZES[size];
  return (
    <svg
      width={px}
      height={px}
      viewBox="0 0 16 16"
      fill="none"
      className={cn("animate-spin shrink-0", className)}
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
