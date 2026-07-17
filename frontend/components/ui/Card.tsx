"use client";
/**
 * components/ui/Card.tsx
 * Dark-theme card wrapper with optional title, subtitle, action slot.
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
        "rounded-xl border border-border-default bg-surface-card",
        "transition-all duration-200",
        hover && "hover:border-border-strong cursor-pointer",
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
