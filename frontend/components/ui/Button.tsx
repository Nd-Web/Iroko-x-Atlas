"use client";
/**
 * components/ui/Button.tsx
 * Reusable button with variants, sizes and loading state.
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
    "bg-brand-500 text-[#0A0A0B] font-bold border border-brand-800",
    "hover:bg-brand-400",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  secondary: [
    "bg-surface-card text-gray-800 border border-border-default",
    "hover:bg-gray-50 hover:border-border-strong",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  danger: [
    "bg-[#EF4444] text-white border border-[#DC2626]",
    "hover:bg-[#DC2626]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  ghost: [
    "bg-transparent text-gray-500 border border-transparent",
    "hover:bg-white/5 hover:text-gray-800",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
};

const sizeStyles: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
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
      className={cn(
        "inline-flex items-center justify-center font-semibold transition-all duration-200 ease-out",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-page",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Spinner size="sm" color={variant === "danger" ? "white" : variant === "primary" ? undefined : "blue"} />
      ) : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
}
