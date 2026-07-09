"use client";
/**
 * components/ui/Button.tsx
 * Reusable button with variants, sizes and loading state.
 * Styled entirely from the design tokens in app/globals.css.
 */
import React from "react";
import { cn } from "@/lib/utils";
import Spinner from "./Spinner";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<Variant, string> = {
  primary: [
    "bg-brand-600 text-white border border-brand-700",
    "hover:bg-brand-700 shadow-xs hover:shadow-sm",
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none",
  ].join(" "),
  secondary: [
    "bg-surface-card text-gray-700 border border-border-strong",
    "hover:bg-gray-50 shadow-xs",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  danger: [
    "bg-danger-500 text-white border border-danger-700",
    "hover:bg-danger-600 shadow-xs",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  ghost: [
    "bg-transparent text-gray-500 border border-transparent",
    "hover:bg-gray-100 hover:text-gray-700",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
};

const sizeStyles: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-lg",
  lg: "h-12 px-6 text-base gap-2.5 rounded-xl",
};

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  leftIcon,
  rightIcon,
  children,
  disabled,
  className,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center font-semibold transition-all duration-200 ease-out",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-page",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size="sm" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
}
