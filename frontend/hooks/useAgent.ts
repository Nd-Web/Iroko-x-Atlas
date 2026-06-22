"use client";

import { useRef, useState, useCallback } from "react";
import {
  createAgentSession,
  sendOffer,
  sendIceCandidates,
  endAgentSession,
} from "@/lib/agent";

export type AgentCallStatus = "idle" | "connecting" | "active" | "ending";

interface UseAgentOptions {
  agentId: string;
  onError?: (msg: string) => void;
}

interface UseAgentReturn {
  status:    AgentCallStatus;
  startCall: () => Promise<void>;
  endCall:   () => Promise<void>;
}

export function useAgent({
  agentId,
  onError,
}: UseAgentOptions): UseAgentReturn {
  const [status, setStatus] = useState<AgentCallStatus>("idle");

  const pcRef         = useRef<RTCPeerConnection | null>(null);
  const sessionIdRef  = useRef<string>("");
  const pcIdRef       = useRef<string>("");
  const pendingRef    = useRef<RTCIceCandidateInit[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flushCandidates = useCallback(async () => {
    if (!pendingRef.current.length || !sessionIdRef.current || !pcIdRef.current) return;
    const batch = [...pendingRef.current];
    pendingRef.current = [];
    await sendIceCandidates(sessionIdRef.current, pcIdRef.current, batch).catch(() => {});
  }, []);

  const endCall = useCallback(async () => {
    if (status === "idle") return;
    setStatus("ending");

    if (flushTimerRef.current) clearTimeout(flushTimerRef.current);

    try {
      pcRef.current?.close();
      pcRef.current = null;
      if (sessionIdRef.current) await endAgentSession(sessionIdRef.current);
    } finally {
      sessionIdRef.current = "";
      pcIdRef.current      = "";
      pendingRef.current   = [];
      setStatus("idle");
    }
  }, [status]);

  const startCall = useCallback(async () => {
    if (status !== "idle") return;
    setStatus("connecting");

    try {
      const { session_id, ice_config } = await createAgentSession(agentId);
      sessionIdRef.current = session_id;

      const pc = new RTCPeerConnection({ iceServers: ice_config.iceServers });
      pcRef.current = pc;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getAudioTracks().forEach((t) => pc.addTrack(t, stream));

      pc.ontrack = (evt) => {
        const audio = new Audio();
        audio.srcObject = evt.streams[0];
        audio.play().catch(() => {});
      };

      pc.onicecandidate = (evt) => {
        if (!evt.candidate) return;
        pendingRef.current.push({
          candidate:     evt.candidate.candidate,
          sdpMid:        evt.candidate.sdpMid        ?? "0",
          sdpMLineIndex: evt.candidate.sdpMLineIndex ?? 0,
        });
        if (flushTimerRef.current) clearTimeout(flushTimerRef.current);
        flushTimerRef.current = setTimeout(flushCandidates, 150);
      };

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;
        if (s === "connected")                                         setStatus("active");
        if (s === "disconnected" || s === "failed" || s === "closed") setStatus("idle");
      };

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const answer = await sendOffer(session_id, offer.sdp!);
      pcIdRef.current = answer.pc_id;

      await pc.setRemoteDescription({ type: answer.type, sdp: answer.sdp });
      await flushCandidates();

    } catch (err) {
      const msg = (err as Error).message ?? "Failed to start voice call";
      onError?.(msg);
      pcRef.current?.close();
      pcRef.current        = null;
      sessionIdRef.current = "";
      pcIdRef.current      = "";
      pendingRef.current   = [];
      setStatus("idle");
    }
  }, [agentId, status, flushCandidates, onError]);

  return { status, startCall, endCall };
}
