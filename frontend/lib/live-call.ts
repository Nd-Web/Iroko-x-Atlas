/**
 * GPT-Live call logic for the voice compliance agent, kept free of React and
 * WebRTC so it can be tested on its own (tests/live-call.test.cjs).
 *
 * With client delegation, GPT-Live decides when a compliance check is needed and
 * sends session.delegation.created. That event carries no task text, so the
 * question is taken from the caller's own transcript. GPT-Live can delegate
 * before the caller finishes speaking, so the check waits for a pause first.
 * The verdict goes back as session.commentary.append for the agent to speak.
 */
import type { ComplianceVerdict } from "@/lib/agent";

export interface LiveServerEvent {
  type?: string;
  delta?: string;
  delegation?: { id?: string; target?: string };
  reason?: string;
}

export interface LiveCallOptions {
  /** Sends a client event over the "oai-events" data channel. */
  send:       (event: Record<string, unknown>) => void;
  check:      (question: string) => Promise<ComplianceVerdict>;
  greeting?:  string;
  onVerdict?: (verdict: ComplianceVerdict) => void;
  onClosed?:  (reason?: string) => void;
  /** Silence that ends the caller's turn. */
  quietMs?:   number;
  /** Longest wait for that silence before checking anyway. */
  maxWaitMs?: number;
  now?:       () => number;
  sleep?:     (ms: number) => Promise<void>;
}

// Commentary content is capped at 500 tokens; this stays well inside it.
const MAX_RESULT_CHARS = 1500;
const MAX_QUESTION_CHARS = 1500;

export function describeVerdict(verdict: ComplianceVerdict): string {
  const parts = [`Iroko compliance engine result. Verdict: ${verdict.verdict}.`];
  if (verdict.regulation) parts.push(`Regulation: ${verdict.regulation}.`);
  if (verdict.reasoning) parts.push(`Reasoning: ${verdict.reasoning}`);
  if (verdict.source) parts.push(`Source document: ${verdict.source}.`);
  if (verdict.evidence) parts.push(`Rule as written: "${verdict.evidence}"`);
  if (verdict.flags?.length) parts.push(`Flags: ${verdict.flags.slice(0, 4).join("; ")}.`);
  return parts.join(" ").slice(0, MAX_RESULT_CHARS);
}

export function createLiveCall({
  send,
  check,
  greeting = "",
  onVerdict,
  onClosed,
  quietMs = 1200,
  maxWaitMs = 8000,
  now = () => Date.now(),
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}: LiveCallOptions) {
  let heard = "";        // caller's words since the last check began
  let recent = "";       // rolling caller transcript, for a re-asked question
  let lastHeardAt = 0;
  let lastCheck: Promise<string> | null = null;

  async function waitForPause() {
    const started = now();
    while (now() - lastHeardAt < quietMs && now() - started < maxWaitMs) await sleep(150);
  }

  async function runCheck(question: string): Promise<string> {
    if (!question) {
      return "No question was heard. Ask the caller to describe the action, product, or practice to assess.";
    }
    try {
      const verdict = await check(question.slice(-MAX_QUESTION_CHARS));
      onVerdict?.(verdict);
      return describeVerdict(verdict);
    } catch (err) {
      const reason = (err as Error)?.message || "unknown error";
      return `Iroko's compliance engine could not complete this check (${reason}). `
        + "Tell the caller the check failed and ask them to try again. Do not give a verdict from memory.";
    }
  }

  async function answerDelegation(delegationId: string) {
    await waitForPause();
    let result: string;
    if (!heard.trim() && lastCheck) {
      // Delegated again with nothing new said: same question, same answer.
      result = await lastCheck;
    } else {
      const question = heard.trim() || recent.trim();
      heard = "";
      lastCheck = runCheck(question);
      result = await lastCheck;
    }
    send({ type: "session.commentary.append", delegation_id: delegationId, content: result });
  }

  return {
    handle(event: LiveServerEvent): Promise<void> | void {
      switch (event.type) {
        case "session.started":
          if (greeting) {
            send({ type: "session.commentary.append", delegation_id: null,
                   content: `Greet the caller in one short sentence: ${greeting}` });
          }
          return;
        case "session.input_transcript.delta":
          heard += event.delta ?? "";
          recent = (recent + (event.delta ?? "")).slice(-MAX_QUESTION_CHARS);
          lastHeardAt = now();
          return;
        case "session.delegation.created":
          if (event.delegation?.target === "client" && event.delegation.id) {
            return answerDelegation(event.delegation.id);
          }
          return;
        case "session.closed":
          onClosed?.(event.reason);
          return;
      }
    },
  };
}
