/**
 * AethexAI client helpers.
 * All calls go through /api/aethex/* (server-side proxy) so the API key
 * never leaves the server.
 */

const PROXY = "/api/aethex";

// ─── Transcription ────────────────────────────────────────────────────────────

// ── WAV encoding helpers ──────────────────────────────────────────────────────
// AethexAI transcribe rejects audio/webm (MediaRecorder default). We decode the
// webm blob with AudioContext then re-encode to WAV (16-bit PCM mono).

function writeStr(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function encodeWav(decoded: AudioBuffer): Blob {
  const pcm        = decoded.getChannelData(0); // mix to mono via first channel
  const sampleRate = decoded.sampleRate;
  const numSamples = pcm.length;
  const dataSize   = numSamples * 2;            // 16-bit = 2 bytes/sample
  const buf        = new ArrayBuffer(44 + dataSize);
  const v          = new DataView(buf);

  writeStr(v,  0, "RIFF");
  v.setUint32( 4, 36 + dataSize, true);
  writeStr(v,  8, "WAVE");
  writeStr(v, 12, "fmt ");
  v.setUint32(16, 16,         true);  // chunk size
  v.setUint16(20,  1,         true);  // PCM
  v.setUint16(22,  1,         true);  // mono
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true); // byte rate
  v.setUint16(32,  2,         true);  // block align
  v.setUint16(34, 16,         true);  // bits per sample
  writeStr(v, 36, "data");
  v.setUint32(40, dataSize,   true);

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
  // Convert webm/opus → wav so AethexAI accepts it
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

// ─── TTS ──────────────────────────────────────────────────────────────────────

const TAREK_VOICE = "29f3ade2-b500-543c-a7a7-827642ac09e7";

export async function speakText(text: string, voiceId = TAREK_VOICE): Promise<void> {
  try {
    const res = await fetch(`${PROXY}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice_id: voiceId, streaming: false }),
    });

    if (!res.ok) return;

    const arrayBuffer = await res.arrayBuffer();
    if (!arrayBuffer.byteLength) return;

    const audioCtx = new AudioContext();
    const decoded  = await audioCtx.decodeAudioData(arrayBuffer);
    const source   = audioCtx.createBufferSource();
    source.buffer  = decoded;
    source.connect(audioCtx.destination);

    await new Promise<void>((resolve) => {
      source.onended = () => resolve();
      source.start(0);
    });
  } catch {
    // TTS is enhancement-only — never throw
  }
}

// ─── Agent WebRTC session helpers ─────────────────────────────────────────────

export interface AethexIceConfig {
  iceServers: RTCIceServer[];
}

export interface AethexSessionResponse {
  session_id: string;
  ice_config: AethexIceConfig;
}

export interface AethexOfferResponse {
  sdp:   string;
  type:  RTCSdpType;
  pc_id: string;
}

export async function createAgentSession(agentId: string): Promise<AethexSessionResponse> {
  const res = await fetch(`${PROXY}/conversation/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `Session create failed (${res.status})`);
  }
  return res.json() as Promise<AethexSessionResponse>;
}

export async function sendOffer(
  sessionId: string,
  sdp: string
): Promise<AethexOfferResponse> {
  const res = await fetch(`${PROXY}/conversation/${sessionId}/offer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp, type: "offer" }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `SDP offer failed (${res.status})`);
  }
  return res.json() as Promise<AethexOfferResponse>;
}

export async function sendIceCandidates(
  sessionId: string,
  pcId: string,
  candidates: RTCIceCandidateInit[]
): Promise<void> {
  // AethexAI expects snake_case keys, not the camelCase RTCIceCandidateInit shape
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
  }).catch(() => { /* best-effort */ });
}
