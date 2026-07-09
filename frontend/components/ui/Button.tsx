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
    "bg-gradient-to-r from-[#3B7BF6] to-[#2563EB]",
    "text-white border border-[#1D4ED8]",
    "hover:from-[#2563EB] hover:to-[#1D4ED8]",
    "shadow-[0_0_20px_rgba(59,123,246,0.25)]",
    "hover:shadow-[0_0_28px_rgba(59,123,246,0.4)]",
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none",
  ].join(" "),
  secondary: [
    "bg-[#1a1d27] text-[#E5E7EB] border border-white/10",
    "hover:bg-[#22263a] hover:border-white/20",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  danger: [
    "bg-[#EF4444] text-white border border-[#DC2626]",
    "hover:bg-[#DC2626]",
    "shadow-[0_0_12px_rgba(239,68,68,0.2)]",
    "hover:shadow-[0_0_20px_rgba(239,68,68,0.35)]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
  ghost: [
    "bg-transparent text-[#9CA3AF] border border-transparent",
    "hover:bg-white/5 hover:text-[#E5E7EB]",
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
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3B7BF6] focus-visible:ring-offset-2 focus-visible:ring-offset-[#080B14]",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Spinner size="sm" color={variant === "primary" || variant === "danger" ? "white" : "blue"} />
      ) : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
}
