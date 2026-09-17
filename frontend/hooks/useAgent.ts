"use client";

import { useRef, useState, useCallback } from "react";
import {
  getRealtimeSession,
  negotiateWebRTC,
  runComplianceCheck,
  type ComplianceVerdict,
} from "@/lib/agent";

export type AgentCallStatus = "idle" | "connecting" | "active" | "ending";

interface UseAgentOptions {
  instructions?: string;
  onError?:      (msg: string) => void;
  /** Fires when the agent runs a compliance check, so the UI can show the verdict card. */
  onVerdict?:    (verdict: ComplianceVerdict) => void;
}

interface UseAgentReturn {
  status:    AgentCallStatus;
  startCall: () => Promise<void>;
  endCall:   () => Promise<void>;
}

export function useAgent({
  instructions = "",
  onError,
  onVerdict,
}: UseAgentOptions): UseAgentReturn {
  const [status, setStatus] = useState<AgentCallStatus>("idle");

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);

  const endCall = useCallback(async () => {
    if (status === "idle") return;
    setStatus("ending");

    dcRef.current?.close();
    dcRef.current = null;
    pcRef.current?.close();
    pcRef.current = null;
    setStatus("idle");
  }, [status]);

  const startCall = useCallback(async () => {
    if (status !== "idle") return;
    setStatus("connecting");

    try {
      const { clientSecret, callsUrl, greeting } = await getRealtimeSession(instructions);

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getAudioTracks().forEach((t) => pc.addTrack(t, stream));

      pc.ontrack = (evt) => {
        const audio = new Audio();
        audio.srcObject = evt.streams[0];
        audio.play().catch(() => {});
      };

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;
        if (s === "connected")                                         setStatus("active");
        if (s === "disconnected" || s === "failed" || s === "closed") setStatus("idle");
      };

      // Must exist before the offer so Azure negotiates it into the SDP.
      const dc = pc.createDataChannel("realtime-channel");
      dcRef.current = dc;

      dc.addEventListener("open", () => {
        if (!greeting) return;
        dc.send(JSON.stringify({
          type: "response.create",
          response: { instructions: `Greet the caller by saying exactly: ${greeting}` },
        }));
      });

      dc.addEventListener("message", async (evt) => {
        let event: { type?: string; name?: string; call_id?: string; arguments?: string };
        try {
          event = JSON.parse(evt.data);
        } catch {
          return;
        }
        if (event.type !== "response.function_call_arguments.done") return;
        if (event.name !== "check_compliance" || !event.call_id) return;

        let output: string;
        try {
          const args = JSON.parse(event.arguments ?? "{}") as {
            text?: string;
            sector?: "network" | "financial";
          };
          const verdict = await runComplianceCheck(args.text ?? "", args.sector ?? "network");
          onVerdict?.(verdict);
          output = JSON.stringify(verdict);
        } catch (err) {
          output = JSON.stringify({ error: (err as Error).message ?? "Compliance check failed" });
        }

        // Hand the result back and let the agent speak it.
        dc.send(JSON.stringify({
          type: "conversation.item.create",
          item: { type: "function_call_output", call_id: event.call_id, output },
        }));
        dc.send(JSON.stringify({ type: "response.create" }));
      });

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const answerSdp = await negotiateWebRTC(callsUrl, clientSecret, offer.sdp!);
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

    } catch (err) {
      const msg = (err as Error).message ?? "Failed to start voice call";
      onError?.(msg);
      dcRef.current?.close();
      dcRef.current = null;
      pcRef.current?.close();
      pcRef.current = null;
      setStatus("idle");
    }
  }, [instructions, status, onError, onVerdict]);

  return { status, startCall, endCall };
}
