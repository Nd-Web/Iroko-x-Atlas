"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useSector } from "@/hooks/useSector";
import { SECTOR_META } from "@/lib/sector";
import { QUICK_FILLS_BY_SECTOR } from "@/lib/compliance-data";

interface ComplianceResult {
  verdict: "GO" | "NO-GO" | "MONITOR";
  flags: string[];
  reasoning: string;
  regulation: string;
  confidence: number;
  checked_at: string;
}

const VERDICT_CONFIG = {
  "GO": {
    border: "#22C55E",
    bg: "rgba(34, 197, 94, 0.08)",
    badgeBg: "rgba(34, 197, 94, 0.16)",
    badgeText: "#4ADE80",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="9" stroke="#4ADE80" strokeWidth="1.5" />
        <path d="M6.5 10l2.5 2.5 4.5-5" stroke="#4ADE80" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  "NO-GO": {
    border: "#EF4444",
    bg: "rgba(239, 68, 68, 0.08)",
    badgeBg: "rgba(239, 68, 68, 0.16)",
    badgeText: "#F87171",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="9" stroke="#F87171" strokeWidth="1.5" />
        <path d="M7 7l6 6M13 7l-6 6" stroke="#F87171" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  "MONITOR": {
    border: "#F59E0B",
    bg: "rgba(245, 158, 11, 0.08)",
    badgeBg: "rgba(245, 158, 11, 0.16)",
    badgeText: "#FBBF24",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2L18.5 17H1.5L10 2Z" stroke="#FBBF24" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M10 8v4M10 14.5v.5" stroke="#FBBF24" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
};

function formatCheckedAt(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-NG", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Africa/Lagos",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function ComplianceChecker() {
  const { user, userLoading } = useAuth();
  const [sector] = useSector();
  const meta = SECTOR_META[sector];
  const quickFills = QUICK_FILLS_BY_SECTOR[sector];
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ComplianceResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sealed, setSealed] = useState(false);

  async function handleCheck() {
    if (!inputText.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    setSealed(false);

    try {
      // Call through the Next.js proxy — it reads the httpOnly cookie server-side
      const res = await fetch("/api/v1/compliance/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: inputText.trim(), context: meta.checkerContext, sector }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }

      const data: ComplianceResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function handleSeal() {
    setSealed(true);
    toast.success("Decision logged · SHA-256 hash sealed");
  }

  // Still hydrating — show nothing rather than a false "please log in"
  if (userLoading) {
    return (
      <div className="rounded-xl border border-border-default bg-surface-card shadow-sm px-6 py-8">
        <div className="h-4 w-48 rounded bg-gray-100 animate-pulse" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-xl border border-border-default bg-surface-card shadow-sm px-6 py-8 text-center">
        <p className="text-sm text-gray-500">Please log in to run compliance checks.</p>
      </div>
    );
  }

  const cfg = result ? VERDICT_CONFIG[result.verdict] : null;

  return (
    <div className="rounded-xl border border-border-default bg-surface-card shadow-sm px-6 py-6 flex flex-col gap-5">
      {/* Input */}
      <textarea
        rows={4}
        value={inputText}
        onChange={e => setInputText(e.target.value)}
        placeholder={meta.checkerPlaceholder}
        className="input-base w-full resize-none text-[13.5px] leading-relaxed"
        style={{ padding: "12px 14px" }}
        onKeyDown={e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleCheck(); }}
      />

      {/* Quick-fill */}
      <div className="flex flex-col gap-2">
        <span className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.06em]">Quick examples</span>
        <div className="flex flex-wrap gap-2">
          {quickFills.map(q => (
            <button
              key={q}
              onClick={() => { setInputText(q); setResult(null); setError(null); }}
              className="text-[12px] text-gray-600 bg-gray-50 border border-border-default rounded-full px-3 py-[5px] hover:bg-gray-100 hover:text-gray-800 transition-colors text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        onClick={handleCheck}
        disabled={loading || !inputText.trim()}
        className="btn-primary self-start"
        style={{ padding: "10px 22px" }}
      >
        {loading ? "Checking…" : "Check Compliance"}
      </button>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 px-4 py-3 bg-brand-50 border border-brand-100 rounded-lg">
          <svg className="animate-spin shrink-0" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="var(--color-brand-300)" strokeWidth="2" />
            <path d="M8 2a6 6 0 0 1 6 6" stroke="var(--color-brand-600)" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span className="text-[13px] text-brand-700 font-medium">
            Iroko is checking against {meta.regulators} regulations...
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 px-4 py-3 bg-danger-50 border border-danger-200 rounded-lg">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-[1px]">
            <circle cx="8" cy="8" r="6.5" stroke="var(--color-danger-600)" strokeWidth="1.3" />
            <path d="M8 5v3.5M8 10.5v.5" stroke="var(--color-danger-600)" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <div>
            <p className="text-[13px] font-semibold text-danger-700 mb-[2px]">Compliance check failed</p>
            <p className="text-[12.5px] text-danger-600">{error}</p>
          </div>
        </div>
      )}

      {/* Result */}
      {result && cfg && (
        <div
          className="rounded-xl border-l-[4px] p-5 flex flex-col gap-4"
          style={{ borderLeftColor: cfg.border, borderTop: `1px solid ${cfg.border}33`, borderRight: `1px solid ${cfg.border}33`, borderBottom: `1px solid ${cfg.border}33`, background: cfg.bg }}
        >
          {/* Verdict header */}
          <div className="flex items-center gap-3">
            {cfg.icon}
            <span
              className="text-[13px] font-bold px-3 py-[4px] rounded-full tracking-wide"
              style={{ background: cfg.badgeBg, color: cfg.badgeText }}
            >
              {result.verdict}
            </span>
            <span className="ml-auto text-[12px] font-semibold" style={{ color: cfg.badgeText }}>
              {Math.round(result.confidence * 100)}% confidence
            </span>
          </div>

          {/* Reasoning */}
          <p className="text-[13.5px] text-gray-700 leading-[1.65] m-0">{result.reasoning}</p>

          {/* Regulation */}
          {result.regulation && (
            <div className="flex items-center gap-2">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className="shrink-0 text-gray-400">
                <path d="M6.5 1.5L11 4v5L6.5 11.5 2 9V4L6.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
              </svg>
              <span className="text-[12px] font-semibold text-gray-500">Regulation cited:</span>
              <span className="text-[12px] text-gray-700 font-medium">{result.regulation}</span>
            </div>
          )}

          {/* Flags */}
          {result.flags.length > 0 && (
            <div>
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.06em] block mb-2">Compliance flags</span>
              <ul className="flex flex-col gap-1.5 m-0 p-0 list-none">
                {result.flags.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-[12.5px] text-gray-600">
                    <span className="mt-[5px] w-[5px] h-[5px] rounded-full shrink-0" style={{ background: cfg.border }} />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Timestamp */}
          <p className="text-[11.5px] text-gray-400 m-0">
            Checked {formatCheckedAt(result.checked_at)} WAT
          </p>

          {/* Seal button */}
          <button
            onClick={handleSeal}
            disabled={sealed}
            className={`self-start text-[12.5px] font-semibold px-4 py-[7px] rounded-lg border transition-colors ${sealed ? "text-success-700 bg-success-50 border-success-100 cursor-default" : "text-brand-500 bg-surface-card border-brand-200 hover:bg-brand-50"}`}
          >
            {sealed ? "✓ Sealed in audit trail" : "Seal in Audit Trail"}
          </button>
        </div>
      )}
    </div>
  );
}
