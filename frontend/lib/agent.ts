/**
 * Iroko AI voice client helpers.
 * TTS/STT go through /api/voice/* (server-side proxy, cookie-authenticated
 * like the rest of the app). The live call uses GPT-Live over WebRTC: the
 * browser's SDP offer goes through the backend, which holds the Azure key,
 * and the media then flows directly between the browser and Azure.
 */

const PROXY = "/api/voice";

// ─── Transcription ────────────────────────────────────────────────────────────

function writeStr(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function encodeWav(decoded: AudioBuffer): Blob {
  const pcm        = decoded.getChannelData(0);
  const sampleRate = decoded.sampleRate;
  const numSamples = pcm.length;
  const dataSize   = numSamples * 2;
  const buf        = new ArrayBuffer(44 + dataSize);
  const v          = new DataView(buf);

  writeStr(v,  0, "RIFF");
  v.setUint32( 4, 36 + dataSize, true);
  writeStr(v,  8, "WAVE");
  writeStr(v, 12, "fmt ");
  v.setUint32(16, 16,              true);
  v.setUint16(20,  1,              true);
  v.setUint16(22,  1,              true);
  v.setUint32(24, sampleRate,      true);
  v.setUint32(28, sampleRate * 2,  true);
  v.setUint16(32,  2,              true);
  v.setUint16(34, 16,              true);
  writeStr(v, 36, "data");
  v.setUint32(40, dataSize,        true);

  let off = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    v.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    off += 2;
  }

  return new Blob([buf], { type: "audio/wav" });
}

async function toWav(blob: Blob): Promise<Blob> {
  const arrayBuf = await blob.arrayBuffer();
  const ctx      = new AudioContext();
  try {
    const decoded = await ctx.decodeAudioData(arrayBuf);
    return encodeWav(decoded);
  } finally {
    await ctx.close().catch(() => {});
  }
}

export async function transcribeAudio(audioBlob: Blob): Promise<string> {
  const wavBlob = await toWav(audioBlob);

  const form = new FormData();
  form.append("file", wavBlob, "recording.wav");

  const res = await fetch(`${PROXY}/transcribe`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({})) as { detail?: string; error?: string };
    throw new Error(detail.detail ?? detail.error ?? `Transcription failed (${res.status})`);
  }

  const data = await res.json() as { transcript?: string; text?: string };
  const text = data.transcript ?? data.text ?? "";
  if (!text) throw new Error("Empty transcript");
  return text;
}

// ─── TTS — Azure Realtime preset voice ─────────────────────────────────────────

const DEFAULT_VOICE = "marin"; // Azure Realtime preset — no Nigerian-accented voice is available

let _currentAudio: HTMLAudioElement | null = null;

export async function speakText(text: string, voice = DEFAULT_VOICE): Promise<void> {
  if (typeof window === "undefined") return;

  _currentAudio?.pause();
  _currentAudio = null;

  try {
    const res = await fetch(`${PROXY}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice }),
    });

    if (!res.ok) throw new Error(`TTS ${res.status}`);

    const arrayBuffer = await res.arrayBuffer();
    if (!arrayBuffer.byteLength) return;

    const blob  = new Blob([arrayBuffer], { type: "audio/mpeg" });
    const url   = URL.createObjectURL(blob);
    const audio = new Audio(url);
    _currentAudio = audio;

    await new Promise<void>((resolve) => {
      audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
      audio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
      audio.play().catch(() => resolve());
    });
  } catch {
    // TTS is enhancement-only — never throw
  }
}

// ─── GPT-Live WebRTC session ────────────────────────────────────────────────────
//
// One SDP offer/answer round trip through the backend, which creates the
// session (persona, voice, client delegation) with the Azure key.

export interface LiveSession {
  sdp:       string;
  sessionId: string | null;
  greeting:  string;
}

export async function createLiveSession(offerSdp: string): Promise<LiveSession> {
  const res = await fetch(`${PROXY}/live-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp: offerSdp }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `Voice session failed (${res.status})`);
  }
  const data = await res.json() as { sdp: string; session_id?: string | null; greeting?: string };
  return { sdp: data.sdp, sessionId: data.session_id ?? null, greeting: data.greeting ?? "" };
}

// ─── Compliance engine (answers the voice agent's delegations) ─────────────────

export interface ComplianceVerdict {
  verdict:    string;
  flags:      string[];
  reasoning:  string;
  regulation: string;
  confidence: number;
  checked_at: string;
  /** The deciding rule, verbatim from a document in Iroko's library. */
  evidence?:  string | null;
  /** That document's title. */
  source?:    string | null;
}

export async function runComplianceCheck(
  text: string,
  sector: "financial" | "network" = "financial"
): Promise<ComplianceVerdict> {
  const res = await fetch(`${PROXY}/compliance-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, sector }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `Compliance check failed (${res.status})`);
  }
  return res.json() as Promise<ComplianceVerdict>;
}
