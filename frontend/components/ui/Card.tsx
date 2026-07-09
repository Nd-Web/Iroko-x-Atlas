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
        "rounded-xl border border-white/[0.06] bg-[#0F1320]",
        "transition-all duration-200",
        hover && "hover:border-white/[0.12] hover:shadow-[0_0_24px_rgba(59,123,246,0.08)] cursor-pointer",
        !noPad && "p-5",
        className,
      )}
    >
      {(title || action) && (
        <div className={cn("flex items-start justify-between gap-3", !noPad && children ? "mb-4" : "")}>
          <div>
            {title && (
              <h3 className="text-[15px] font-semibold text-[#E5E7EB] leading-tight">{title}</h3>
            )}
            {subtitle && (
              <p className="text-xs text-[#6B7280] mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
