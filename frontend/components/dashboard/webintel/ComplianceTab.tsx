"use client";
/**
 * components/dashboard/webintel/ComplianceTab.tsx
 *
 * Tab 2 — Verdict & Compliance: NCC/NDPA compliance checker,
 * verdict output card, PDF brief download, and the API key panel.
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  type FC,
} from "react";
import { useVoiceCompliance } from "@/hooks/useVoiceCompliance";
import VoiceMicButton from "@/components/ui/VoiceMicButton";
import { useAgent } from "@/hooks/useAgent";
import AgentCallButton from "@/components/ui/AgentCallButton";
import type { VerdictOutput } from "./types";
import { verdictMeta } from "./meta";
import { ErrorBanner } from "./primitives";
import { API, getToken, authHeaders, apiFetch } from "./api";

// ─────────────────────────────────────────────────────────────────────────────
// Verdict Output Card
// ─────────────────────────────────────────────────────────────────────────────

const VerdictCard: FC<{ output: VerdictOutput }> = ({ output }) => {
  const meta       = verdictMeta(output.verdict);
  const violations = output.violations ?? [];
  const actions    = output.recommended_actions ?? [];
  const nccRefs    = output.ncc_refs ?? violations.map((v) => v.regulation_id).filter(Boolean);

  return (
    <div className={`rounded-2xl overflow-hidden border ${meta.border} ${meta.glow}`}>
      {/* Verdict banner */}
      <div className={`flex items-center gap-4 px-6 py-5 ${meta.bannerBg}`}>
        <span className={meta.iconText} aria-hidden="true">{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <div className={`text-[22px] font-black tracking-tight leading-tight ${meta.text}`}>
            {output.verdict}
          </div>
          <p className={`text-[13px] mt-0.5 opacity-80 ${meta.text}`}>
            {meta.label}
          </p>
        </div>
        {output.confidence_score !== undefined && (
          <div className={`flex flex-col items-end shrink-0 ${meta.text}`}>
            <span className="text-[28px] font-black leading-none">
              {Math.round((output.confidence_score ?? 0) * 100)}%
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
              Confidence
            </span>
          </div>
        )}
      </div>

      {/* Details section */}
      <div className="px-6 py-5 space-y-5 bg-surface-card">
        {/* Summary */}
        {output.finding?.summary && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider mb-2 text-gray-400">
              Finding Summary
            </p>
            <p className="text-[13px] leading-relaxed text-gray-500">
              {output.finding.summary}
            </p>
          </div>
        )}

        {/* NCC/NDPA References */}
        {nccRefs.length > 0 && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider mb-2 text-gray-400">
              NCC/NDPA Regulation References
            </p>
            <div className="flex flex-wrap gap-2">
              {nccRefs.map((ref, i) => (
                <span
                  key={i}
                  className="text-[11px] font-mono font-semibold px-2.5 py-1 rounded-lg bg-info-50 border border-[rgba(56,189,248,0.25)] text-info-500"
                >
                  {ref}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Violations */}
        {violations.length > 0 && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider mb-2 text-gray-400">
              Violations Detected
            </p>
            <div className="space-y-2">
              {violations.map((v, i) => (
                <div
                  key={i}
                  className="flex gap-3 px-3 py-2.5 rounded-xl bg-[rgba(239,68,68,0.06)] border border-[rgba(239,68,68,0.15)]"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5 text-[#EF4444]" aria-hidden="true">
                    <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
                    <path d="M8 6.5v2.5M8 11h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                  </svg>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {v.regulation_id && (
                        <span className="text-[10px] font-mono font-bold text-[#EF4444]">
                          {v.regulation_id}
                        </span>
                      )}
                      {v.section && (
                        <span className="text-[10px] text-gray-400">
                          § {v.section}
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] mt-0.5 leading-snug text-gray-500">
                      {v.reason}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommended actions */}
        {actions.length > 0 && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider mb-2 text-gray-400">
              Recommended Actions
            </p>
            <ol className="space-y-2">
              {actions.map((action, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black mt-0.5 bg-info-50 text-info-500 border border-[rgba(56,189,248,0.25)]">
                    {i + 1}
                  </span>
                  <p className="text-[13px] leading-snug text-gray-800">
                    {action}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Verdict & Compliance tab
// ─────────────────────────────────────────────────────────────────────────────

const LAST_VERDICT_KEY   = "iroko_last_verdict";
const LAST_DECISION_KEY  = "iroko_last_decision";

const ComplianceTab: FC = () => {
  // Restore last compliance check from localStorage so Download always reflects the last result
  const [decisionText, setDecisionText] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(LAST_DECISION_KEY) ?? "";
  });
  const [checking,    setChecking]    = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [verdict,     setVerdict]     = useState<VerdictOutput | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const stored = localStorage.getItem(LAST_VERDICT_KEY);
      return stored ? (JSON.parse(stored) as VerdictOutput) : null;
    } catch {
      return null;
    }
  });
  const [error,       setError]       = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ── Voice compliance ───────────────────────────────────────────────────────
  const voiceEnabled = process.env.NEXT_PUBLIC_VOICE_ENABLED !== "false";
  // apiKeyRef lets the hook always read the latest key without re-mounting
  const apiKeyRef = useRef<string>("");

  const handleVoiceVerdict = useCallback((v: import("@/hooks/useVoiceCompliance").VerdictResponse) => {
    const asVerdictOutput = {
      verdict:             v.verdict,
      compliant:           v.verdict === "GO",
      confidence_score:    v.confidence,
      violations:          v.flags.map((f) => ({ regulation_id: "", section: "", reason: f })),
      recommended_actions: [],
      ncc_refs:            v.regulation ? [v.regulation] : [],
      finding:             { summary: v.reasoning },
    };
    setVerdict(asVerdictOutput);
    localStorage.setItem(LAST_VERDICT_KEY, JSON.stringify(asVerdictOutput));
  }, []);

  const {
    isListening,
    isProcessing: voiceProcessing,
    transcript,
    error: voiceError,
    startListening,
    stopListening,
  } = useVoiceCompliance({
    userApiKey: apiKeyRef.current,
    onVerdict:  handleVoiceVerdict,
  });

  // Populate textarea when transcript arrives
  useEffect(() => {
    if (transcript) {
      setDecisionText(transcript);
      localStorage.setItem(LAST_DECISION_KEY, transcript);
    }
  }, [transcript]);

  // ── AethexAI live voice agent ──────────────────────────────────────────────
  const [agentError, setAgentError] = useState<string | null>(null);
  const { status: agentStatus, startCall, endCall } = useAgent({
    agentId: process.env.NEXT_PUBLIC_IROKO_AGENT_ID ?? "9aad19b0-5d6e-4306-ac66-cbc8e2486cae",
    onError: (msg) => setAgentError(msg),
  });

  // ── API key state ──────────────────────────────────────────────────────────
  const [apiKey,     setApiKey]     = useState<string | null>(null);
  const [keyVisible, setKeyVisible] = useState(false);
  const [keyCopied,  setKeyCopied]  = useState(false);
  const [keyLoading, setKeyLoading] = useState(false);
  const [keyError,   setKeyError]   = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("atlas_user");
      if (raw) {
        const user = JSON.parse(raw) as Record<string, unknown>;
        const k = user?.api_key;
        if (typeof k === "string" && k) { setApiKey(k); apiKeyRef.current = k; }
      }
    } catch { /* ignore */ }
  }, []);

  const handleGenerateKey = async () => {
    setKeyLoading(true);
    setKeyError(null);
    try {
      const res = await fetch("/api/auth/generate-key", {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
      }
      const data = await res.json() as { key?: unknown; api_key?: string };
      // Proxy wraps backend response as { key: { api_key, message, ... } }
      const newKey: string =
        typeof data.key === "string"
          ? data.key
          : (data.key as Record<string, string> | null)?.api_key
            ?? data.api_key
            ?? "";
      setApiKey(newKey);
      apiKeyRef.current = newKey;
      setKeyVisible(true);
      try {
        const raw  = localStorage.getItem("atlas_user");
        const user = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
        localStorage.setItem("atlas_user", JSON.stringify({ ...user, api_key: newKey }));
      } catch { /* ignore */ }
    } catch (e) {
      setKeyError((e as Error).message ?? "Failed to generate key");
    } finally {
      setKeyLoading(false);
    }
  };

  const handleCopyKey = async () => {
    if (!apiKey) return;
    await navigator.clipboard.writeText(apiKey);
    setKeyCopied(true);
    setTimeout(() => setKeyCopied(false), 2000);
  };

  const maskedKey = apiKey
    ? `${apiKey.slice(0, 12)}${"•".repeat(Math.max(0, apiKey.length - 16))}${apiKey.slice(-4)}`
    : null;

  const handleCheck = async () => {
    if (!decisionText.trim()) return;
    setChecking(true);
    setError(null);
    setVerdict(null);
    try {
      const result = await apiFetch<VerdictOutput>("/check-compliance", {
        method: "POST",
        body:   JSON.stringify({ decision_text: decisionText }),
      });
      setVerdict(result);
      // Persist so Download works even after a page refresh
      localStorage.setItem(LAST_VERDICT_KEY,  JSON.stringify(result));
      localStorage.setItem(LAST_DECISION_KEY, decisionText);
    } catch (e) {
      setError((e as Error).message ?? "Compliance check failed.");
    } finally {
      setChecking(false);
    }
  };

  const handleDownloadBrief = async () => {
    setDownloading(true);
    setError(null);
    try {
      let blob: Blob;

      // ── Resolve verdict: prefer React state, fall back to localStorage ──
      // This guards against React closure edge-cases where `verdict` state
      // is transiently null (e.g. during a check) but localStorage still
      // holds the last successful result.
      let activeVerdict: VerdictOutput | null = verdict;
      let activeDecision: string = decisionText;
      if (!activeVerdict) {
        try {
          const stored = localStorage.getItem(LAST_VERDICT_KEY);
          if (stored) activeVerdict = JSON.parse(stored) as VerdictOutput;
          const storedDecision = localStorage.getItem(LAST_DECISION_KEY);
          if (storedDecision) activeDecision = storedDecision;
        } catch { /* ignore parse errors */ }
      }

      if (activeVerdict) {
        // ── A compliance check exists — use the dedicated PDF endpoint ──
        const res = await fetch(`${API}/compliance-pdf`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`,
          },
          body: JSON.stringify({
            verdict:             activeVerdict.verdict,
            compliant:           activeVerdict.compliant ?? true,
            confidence_score:    activeVerdict.confidence_score ?? null,
            violations:          activeVerdict.violations ?? [],
            recommended_actions: activeVerdict.recommended_actions ?? [],
            ncc_refs:            activeVerdict.ncc_refs ?? [],
            decision_text:       activeDecision,
            summary:             activeVerdict.finding?.summary ?? "",
            workspace_name:      "Enterprise Telecom Operations",
          }),
        });
        if (!res.ok) {
          const detail = await res.text().catch(() => res.statusText);
          throw new Error(`PDF generation failed (${res.status}): ${detail}`);
        }
        blob = await res.blob();
      } else {
        // ── No compliance check ever run — fall back to generic audit brief ──
        const res = await fetch(`${API}/brief?include_audit_trail=true`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
        blob = await res.blob();
      }

      const downloadVerdict = activeVerdict?.verdict;
      const url = URL.createObjectURL(blob);
      const a   = document.createElement("a");
      a.href     = url;
      a.download = downloadVerdict
        ? `iroko-compliance-${downloadVerdict.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.pdf`
        : `iroko-document-intelligence-brief-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Brief download failed: ${(e as Error).message}`);
    } finally {
      setDownloading(false);
    }
  };

  // Auto-grow textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDecisionText(e.target.value);
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`;
  };

  return (
    <div className="flex flex-col gap-6">
    <div className="grid gap-6 grid-cols-2">
      {/* Left: input panel */}
      <div className="flex flex-col gap-5">
        {/* Compliance checker */}
        <div className="rounded-2xl p-6 bg-surface-card border border-border-default">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 bg-info-50 border border-[rgba(56,189,248,0.2)] text-info-500">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                  stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
                <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <h3 className="text-[14px] font-bold text-gray-800">
                NCC/NDPA Compliance Check
              </h3>
              <p className="text-[11px] mt-0.5 text-gray-400">
                Evaluate a decision against the live NCC/NDPA regulatory corpus
              </p>
            </div>
          </div>

          {voiceEnabled && (
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <VoiceMicButton
                isListening={isListening}
                isProcessing={voiceProcessing}
                onStart={startListening}
                onStop={stopListening}
              />
              <AgentCallButton
                status={agentStatus}
                onStart={startCall}
                onEnd={endCall}
              />
              {(voiceError ?? agentError) && (
                <span className="text-[11.5px] text-[#EF4444]">
                  {voiceError ?? agentError}
                </span>
              )}
            </div>
          )}

          <div className="relative">
            <textarea
              ref={textareaRef}
              value={decisionText}
              onChange={handleInput}
              placeholder="Describe a decision or planned action for compliance review…&#10;&#10;e.g. &quot;We plan to launch a new analytics pipeline on MoMo transaction data next quarter — what NDPA obligations apply?&quot;"
              className="w-full resize-none rounded-xl text-[13px] leading-relaxed transition-all duration-200 min-h-[140px] px-4 py-3.5 bg-gray-50 border border-border-default text-gray-800 caret-brand-500 placeholder:text-gray-300 focus:outline-none focus:border-[rgba(255,203,5,0.5)] focus:ring-[3px] focus:ring-[rgba(255,203,5,0.12)]"
            />
            {decisionText.length > 0 && (
              <span className="absolute bottom-3 right-3 text-[10px] text-gray-300">
                {decisionText.length} chars
              </span>
            )}
          </div>

          {error && (
            <div className="mt-3">
              <ErrorBanner message={error} onDismiss={() => setError(null)} />
            </div>
          )}

          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={handleCheck}
              disabled={checking || !decisionText.trim()}
              className={`flex-1 flex items-center justify-center gap-2 h-11 rounded-xl text-[13px] font-bold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.01] active:scale-[0.99] text-[#0A0A0B] border border-transparent ${
                checking
                  ? "bg-brand-400"
                  : "bg-brand-500 hover:bg-brand-400"
              }`}
            >
              {checking ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin" aria-hidden="true">
                    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="2" className="opacity-30"/>
                    <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  Analysing against NCC/NDPA corpus…
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                      stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                    <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Check Compliance
                </>
              )}
            </button>
          </div>
        </div>

        {/* Brief download */}
        <div className="rounded-2xl p-6 bg-surface-card border border-border-default">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-[14px] font-bold text-gray-800">
                Compliance Brief
              </h3>
              <p className="text-[12px] mt-1 leading-relaxed text-gray-400">
                Export a boardroom-ready PDF containing the compliance summary,
                audit trail, and recommended actions for regulatory review.
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-gray-50 border border-border-default text-gray-500">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z"
                  stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
                <path d="M14 2v6h6M8 13h8M8 17h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
              </svg>
            </div>
          </div>

          <button
            onClick={handleDownloadBrief}
            disabled={downloading || checking}
            className={`mt-5 w-full flex items-center justify-center gap-2.5 h-11 rounded-xl text-[13px] font-bold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.01] active:scale-[0.99] border border-border-strong text-gray-800 ${
              downloading
                ? "bg-gray-50"
                : "bg-gray-50 hover:bg-gray-100"
            }`}
          >
            {downloading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin" aria-hidden="true">
                  <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="2" className="opacity-30"/>
                  <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Generating PDF…
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M8 2v8M5 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2.5 11.5v1A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5v-1"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                Download Compliance Brief (PDF)
              </>
            )}
          </button>
        </div>
      </div>

      {/* Right: verdict output */}
      <div className="flex flex-col gap-4">
        {verdict ? (
          <VerdictCard output={verdict} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center rounded-2xl py-20 gap-4 min-h-[380px] bg-gray-50 border border-dashed border-border-default">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-info-50 border border-[rgba(56,189,248,0.15)] text-info-500">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 3L21 7.5V12C21 16.5 17.5 20.5 12 22C6.5 20.5 3 16.5 3 12V7.5L12 3Z"
                  stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="text-center">
              <p className="text-[14px] font-semibold text-gray-800">
                Verdict will appear here
              </p>
              <p className="text-[12px] mt-1 text-gray-400">
                Enter a decision and click Check Compliance
              </p>
            </div>
          </div>
        )}
      </div>
    </div>

    {/* API key panel — full width below the 2-column grid */}
    <div className="rounded-2xl p-6 bg-surface-card border border-border-default">
      <div className="flex items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-[14px] font-bold text-gray-800">
            Compliance API Key
          </h3>
          <p className="text-[11px] mt-0.5 text-gray-400">
            Use with{" "}
            <code className="px-1.5 py-0.5 rounded-md text-[10.5px] font-mono bg-gray-50 text-info-500">
              POST /api/v1/compliance/check
            </code>
          </p>
        </div>
        <button
          onClick={handleGenerateKey}
          disabled={keyLoading}
          className="shrink-0 px-4 py-2 rounded-xl text-[12px] font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed bg-brand-50 border border-brand-200 text-brand-500 hover:bg-brand-100"
        >
          {keyLoading ? "Generating…" : apiKey ? "Regenerate" : "Generate key"}
        </button>
      </div>

      {keyError && (
        <div className="mb-3">
          <ErrorBanner message={keyError} onDismiss={() => setKeyError(null)} />
        </div>
      )}

      {apiKey ? (
        <>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-3 py-2.5 rounded-xl text-[12.5px] font-mono truncate select-all bg-gray-50 border border-border-default text-gray-800">
              {keyVisible ? apiKey : maskedKey}
            </code>
            <button
              onClick={() => setKeyVisible((v) => !v)}
              title={keyVisible ? "Hide" : "Show"}
              aria-label={keyVisible ? "Hide API key" : "Show API key"}
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-colors bg-gray-50 border border-border-default text-gray-400"
            >
              {keyVisible ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
            <button
              onClick={handleCopyKey}
              title="Copy"
              aria-label="Copy API key"
              className={`w-9 h-9 rounded-xl flex items-center justify-center transition-colors border ${
                keyCopied
                  ? "bg-[rgba(16,185,129,0.1)] border-[rgba(16,185,129,0.3)] text-[#10B981]"
                  : "bg-gray-50 border-border-default text-gray-400"
              }`}
            >
              {keyCopied ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              )}
            </button>
          </div>
          <p className="text-[11px] mt-3 text-gray-400">
            Pass as{" "}
            <code className="px-1 py-0.5 rounded text-[10.5px] font-mono bg-gray-50 text-info-500">
              Authorization: Bearer &lt;key&gt;
            </code>
            . Regenerating immediately invalidates the old key.
          </p>
        </>
      ) : (
        <p className="text-[12px] text-gray-500">
          No API key yet.{" "}
          <button
            onClick={handleGenerateKey}
            className="underline text-info-500 bg-transparent border-none cursor-pointer"
          >
            Generate one
          </button>{" "}
          to call the compliance API directly.
        </p>
      )}
    </div>
    </div>
  );
};

export default ComplianceTab;
