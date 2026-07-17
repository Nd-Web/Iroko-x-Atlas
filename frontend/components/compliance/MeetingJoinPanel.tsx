"use client";
/**
 * MeetingJoinPanel — send Iroko into a live Teams/Zoom/Meet call.
 *
 * Paste a meeting link → "Iroko AI" joins the call and greets the room →
 * type a question → Iroko answers ALOUD in the meeting (Nigerian voice),
 * grounded in the corpus. Backed by /api/meeting/* (Recall.ai bridge).
 */
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Phase = "idle" | "joining" | "in_call" | "asking";

export default function MeetingJoinPanel() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [url, setUrl] = useState("");
  const [botId, setBotId] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [question, setQuestion] = useState("");
  const [lastAnswer, setLastAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ enabled: boolean }>("/api/meeting/config")
      .then((d) => setEnabled(d.enabled))
      .catch(() => setEnabled(false));
  }, []);

  const join = useCallback(async () => {
    if (!url.trim()) return;
    setPhase("joining"); setError(null); setLastAnswer(null);
    try {
      const d = await apiFetch<{ bot_id: string; platform: string }>(
        "/api/meeting/join", { method: "POST", body: JSON.stringify({ meeting_url: url.trim() }) });
      setBotId(d.bot_id);
      setPhase("in_call");
    } catch (e) {
      setError((e as Error).message ?? "Could not join the meeting.");
      setPhase("idle");
    }
  }, [url]);

  const ask = useCallback(async () => {
    if (!question.trim() || !botId) return;
    setPhase("asking"); setError(null);
    const q = question.trim();
    try {
      const d = await apiFetch<{ answer: string }>(
        "/api/meeting/ask", { method: "POST", body: JSON.stringify({ bot_id: botId, question: q }) });
      setLastAnswer(d.answer);
      setQuestion("");
    } catch (e) {
      setError((e as Error).message ?? "Iroko couldn't answer that.");
    } finally {
      setPhase("in_call");
    }
  }, [question, botId]);

  const leave = useCallback(async () => {
    if (!botId) return;
    try { await apiFetch("/api/meeting/leave", { method: "POST", body: JSON.stringify({ bot_id: botId }) }); }
    catch { /* best-effort */ }
    setBotId(null); setPhase("idle"); setLastAnswer(null);
  }, [botId]);

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-border-default">
        <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">
          Send Iroko to a meeting
        </h2>
        <p className="text-[11.5px] text-gray-400 mt-[2px]">
          Paste a Microsoft Teams, Zoom, or Google Meet link — Iroko joins the call and answers aloud.
        </p>
      </div>

      <div className="px-5 py-4">
        {enabled === false && (
          <p className="text-xs text-warning-700 bg-warning-50 border border-[rgba(245,158,11,0.25)] rounded-md px-3 py-2">
            Meeting integration isn't switched on for this deployment yet (set <code className="font-mono">RECALL_API_KEY</code> on the server).
          </p>
        )}

        {error && <p className="text-xs text-danger-700 mb-3">{error}</p>}

        {phase === "idle" || phase === "joining" ? (
          <div className="flex items-center gap-2">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") join(); }}
              placeholder="https://teams.live.com/meet/…"
              className="input-base flex-1 text-[13px]"
              disabled={phase === "joining" || enabled === false}
            />
            <button
              onClick={join}
              disabled={phase === "joining" || !url.trim() || enabled === false}
              className="btn-primary py-[8px] px-4 text-[13px] disabled:opacity-50 whitespace-nowrap"
            >
              {phase === "joining" ? "Joining…" : "Join meeting"}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-[12.5px]">
              <span className="w-2 h-2 rounded-full bg-success-500 animate-pulse" />
              <span className="text-gray-800 font-medium">Iroko AI is in the meeting.</span>
              <button onClick={leave} className="ml-auto text-[11px] font-semibold px-2.5 py-1 rounded-lg text-gray-400 border border-border-default hover:bg-white/[0.04]">
                Leave
              </button>
            </div>

            <div className="flex items-center gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && phase !== "asking") ask(); }}
                placeholder="Ask Iroko to answer aloud — e.g. Can we store subscriber data in a US region?"
                className="input-base flex-1 text-[13px]"
                disabled={phase === "asking"}
              />
              <button
                onClick={ask}
                disabled={phase === "asking" || !question.trim()}
                className="btn-primary py-[8px] px-4 text-[13px] disabled:opacity-50 whitespace-nowrap"
              >
                {phase === "asking" ? "Answering…" : "Ask in meeting"}
              </button>
            </div>

            {phase === "asking" && (
              <p className="text-[11.5px] text-gray-400">Iroko is checking the corpus and will speak the answer in the meeting…</p>
            )}
            {lastAnswer && (
              <div className="rounded-lg bg-gray-50 border border-border-default px-3 py-2.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-brand-500 mb-1">Spoken in the meeting</p>
                <p className="text-[12.5px] text-gray-700 leading-relaxed">{lastAnswer}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
