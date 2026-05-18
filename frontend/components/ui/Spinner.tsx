"use client";
/**
 * components/ui/Spinner.tsx
 * Pure CSS animated spinner — no external libraries.
 */
import React from "react";
import { cn } from "@/lib/utils";

type SpinnerSize = "sm" | "md" | "lg";
type SpinnerColor = "white" | "blue" | "amber";

interface SpinnerProps {
  size?: SpinnerSize;
  color?: SpinnerColor;
  className?: string;
}

const sizeMap: Record<SpinnerSize, { px: number; borderWidth: number }> = {
  sm: { px: 16, borderWidth: 2 },
  md: { px: 24, borderWidth: 2.5 },
  lg: { px: 40, borderWidth: 3.5 },
};

const colorMap: Record<SpinnerColor, { track: string; spin: string }> = {
  white: { track: "rgba(255,255,255,0.15)", spin: "#ffffff" },
  blue:  { track: "rgba(59,123,246,0.15)", spin: "#3B7BF6" },
  amber: { track: "rgba(245,158,11,0.15)", spin: "#F59E0B" },
};

export default function Spinner({ size = "md", color = "blue", className }: SpinnerProps) {
  const { px, borderWidth } = sizeMap[size];
  const { track, spin } = colorMap[color];

  return (
    <>
      <div
        className={cn("shrink-0 rounded-full animate-spin", className)}
        style={{
          width: px,
          height: px,
          border: `${borderWidth}px solid ${track}`,
          borderTopColor: spin,
          borderRightColor: spin,
        }}
        role="status"
        aria-label="Loading"
      />
    </>
  );
}
