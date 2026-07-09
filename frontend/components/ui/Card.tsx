"use client";
/**
 * components/ui/Card.tsx
 * Card wrapper with optional title, subtitle, action slot.
 * Styled from the design tokens in app/globals.css.
 */
import React from "react";
import { cn } from "@/lib/utils";

interface CardProps {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
  hover?: boolean;
  noPad?: boolean;
  style?: React.CSSProperties;
}

export default function Card({
  title, subtitle, action, className, children, hover = false, noPad = false, style,
}: CardProps) {
  return (
    <div
      style={style}
      className={cn(
        "rounded-xl border border-border-default bg-surface-card shadow-xs",
        "transition-all duration-200",
        hover && "hover:border-border-strong hover:shadow-sm cursor-pointer",
        !noPad && "p-5",
        className,
      )}
    >
      {(title || action) && (
        <div className={cn("flex items-start justify-between gap-3", !noPad && children ? "mb-4" : "")}>
          <div>
            {title && (
              <h3 className="text-[15px] font-semibold text-gray-900 leading-tight">{title}</h3>
            )}
            {subtitle && (
              <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
