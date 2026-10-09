"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import {
  createLiveSession,
  runComplianceCheck,
  type ComplianceVerdict,
} from "@/lib/agent";
import { createLiveCall, type LiveServerEvent } from "@/lib/live-call";

export type AgentCallStatus = "idle" | "connecting" | "active" | "ending";

interface UseAgentOptions {
  onError?:   (msg: string) => void;
  /** Fires when the agent runs a compliance check, so the UI can show the verdict card. */
  onVerdict?: (verdict: ComplianceVerdict) => void;
}

interface UseAgentReturn {
  status:    AgentCallStatus;
  startCall: () => Promise<void>;
  endCall:   () => Promise<void>;
}

function startErrorMessage(err: unknown): string {
  const e = err as Error;
  if (e?.name === "NotAllowedError") return "Microphone access was blocked. Allow the microphone for this site and try again.";
  if (e?.name === "NotFoundError") return "No microphone was found.";
  return e?.message || "Failed to start voice call";
}

/** Live voice call with the GPT-Live compliance agent (see lib/live-call.ts). */
export function useAgent({ onError, onVerdict }: UseAgentOptions): UseAgentReturn {
  const [status, setStatus] = useState<AgentCallStatus>("idle");

  const pcRef     = useRef<RTCPeerConnection | null>(null);
  const dcRef     = useRef<RTCDataChannel | null>(null);
  const micRef    = useRef<MediaStream | null>(null);
  const audioRef  = useRef<HTMLAudioElement | null>(null);
  const closedRef = useRef<(() => void) | null>(null);

  const teardown = useCallback(() => {
    dcRef.current?.close();
    dcRef.current = null;
    pcRef.current?.close();
    pcRef.current = null;
    micRef.current?.getTracks().forEach((t) => t.stop());
    micRef.current = null;
    if (audioRef.current) audioRef.current.srcObject = null;
    audioRef.current = null;
    setStatus("idle");
  }, []);

  useEffect(() => teardown, [teardown]);

  const endCall = useCallback(async () => {
    if (status === "idle" || status === "ending") return;
    setStatus("ending");
    const dc = dcRef.current;
    if (dc?.readyState === "open") {
      // Graceful close: GPT-Live drains its work and answers session.closed.
      dc.send(JSON.stringify({ type: "session.close" }));
      await new Promise<void>((resolve) => {
        closedRef.current = resolve;
        setTimeout(resolve, 2000);
      });
      closedRef.current = null;
    }
    teardown();
  }, [status, teardown]);

  const startCall = useCallback(async () => {
    if (status !== "idle") return;
    setStatus("connecting");

    try {
      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
      micRef.current = mic;
      mic.getAudioTracks().forEach((t) => pc.addTrack(t, mic));

      pc.ontrack = (evt) => {
        const audio = new Audio();
        audio.srcObject = evt.streams[0];
        audioRef.current = audio;
        audio.play().catch(() => {});
      };

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;
        if (s === "connected") setStatus("active");
        if (s === "disconnected" || s === "failed" || s === "closed") teardown();
      };

      // Must exist before the offer so it is negotiated into the SDP.
      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      const session = await createLiveSession(offer.sdp!);

      const call = createLiveCall({
        send: (event) => { if (dc.readyState === "open") dc.send(JSON.stringify(event)); },
        check: (question) => runComplianceCheck(question, "financial"),
        greeting: session.greeting,
        onVerdict,
        onClosed: () => {
          if (closedRef.current) closedRef.current();
          else teardown();
        },
      });
      dc.addEventListener("message", (evt) => {
        let event: LiveServerEvent;
        try {
          event = JSON.parse(evt.data);
        } catch {
          return;
        }
        void call.handle(event);
      });

      await pc.setRemoteDescription({ type: "answer", sdp: session.sdp });
    } catch (err) {
      onError?.(startErrorMessage(err));
      teardown();
    }
  }, [status, onError, onVerdict, teardown]);

  return { status, startCall, endCall };
}
