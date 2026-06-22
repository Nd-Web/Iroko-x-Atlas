/**
 * Iroko AI agent client helpers.
 * All calls go through /api/agent/* (server-side proxy) so the API key
 * never leaves the server.
 */

const PROXY = "/api/agent";

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

// ─── TTS — neural voice ───────────────────────────────────────────────────────

const DEFAULT_VOICE = "354d8730-388b-5d94-a7e8-9f8bc87dc4fc"; // Ada — Nigerian English, dialect-style

let _currentAudio: HTMLAudioElement | null = null;

export async function speakText(text: string, voiceId = DEFAULT_VOICE): Promise<void> {
  if (typeof window === "undefined") return;

  _currentAudio?.pause();
  _currentAudio = null;

  try {
    const res = await fetch(`${PROXY}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice_id: voiceId, streaming: false }),
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

// ─── Agent WebRTC session helpers ─────────────────────────────────────────────

export interface AgentIceConfig {
  iceServers: RTCIceServer[];
}

export interface AgentSessionResponse {
  session_id: string;
  ice_config: AgentIceConfig;
}

export interface AgentOfferResponse {
  sdp:   string;
  type:  RTCSdpType;
  pc_id: string;
}

export async function createAgentSession(agentId: string): Promise<AgentSessionResponse> {
  const res = await fetch(`${PROXY}/conversation/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `Session create failed (${res.status})`);
  }
  return res.json() as Promise<AgentSessionResponse>;
}

export async function sendOffer(
  sessionId: string,
  sdp: string
): Promise<AgentOfferResponse> {
  const res = await fetch(`${PROXY}/conversation/${sessionId}/offer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp, type: "offer" }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `SDP offer failed (${res.status})`);
  }
  return res.json() as Promise<AgentOfferResponse>;
}

export async function sendIceCandidates(
  sessionId: string,
  pcId: string,
  candidates: RTCIceCandidateInit[]
): Promise<void> {
  const apiCandidates = candidates.map((c) => ({
    candidate:       c.candidate,
    sdp_mid:         c.sdpMid         ?? "0",
    sdp_mline_index: c.sdpMLineIndex  ?? 0,
  }));
  await fetch(`${PROXY}/conversation/${sessionId}/ice`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pc_id: pcId, candidates: apiCandidates }),
  });
}

export async function endAgentSession(sessionId: string): Promise<void> {
  await fetch(`${PROXY}/conversation/${sessionId}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  }).catch(() => {});
}
