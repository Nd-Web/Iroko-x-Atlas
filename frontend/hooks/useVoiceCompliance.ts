"use client";

import { useRef, useState, useCallback } from "react";
import { transcribeAudio, speakText } from "@/lib/aethex";

export interface VerdictResponse {
  verdict: "GO" | "NO-GO" | "MONITOR" | string;
  flags: string[];
  reasoning: string;
  regulation: string;
  confidence: number;
  checked_at: string;
}

interface UseVoiceComplianceOptions {
  userApiKey: string;
  onVerdict: (verdict: VerdictResponse) => void;
}

interface UseVoiceComplianceReturn {
  isListening:   boolean;
  isProcessing:  boolean;
  transcript:    string;
  error:         string | null;
  startListening: () => Promise<void>;
  stopListening:  () => void;
}

export function useVoiceCompliance({
  userApiKey,
  onVerdict,
}: UseVoiceComplianceOptions): UseVoiceComplianceReturn {
  const [isListening,  setIsListening]  = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript,   setTranscript]   = useState("");
  const [error,        setError]        = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const streamRef        = useRef<MediaStream | null>(null);

  const runComplianceCheck = useCallback(async (text: string) => {
    setIsProcessing(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/compliance/check", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${userApiKey}`,
        },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? `Request failed (${res.status})`);
      }

      const result = await res.json() as VerdictResponse;
      onVerdict(result);

      // Read verdict aloud
      const { verdict, reasoning, regulation } = result;
      let speech: string;
      if (verdict === "GO") {
        speech = "Compliant. No regulatory issues identified.";
      } else if (verdict === "MONITOR") {
        speech = `Monitor required. ${reasoning}. Relevant regulation: ${regulation}.`;
      } else {
        speech = `Non-compliant. ${reasoning}. This violates ${regulation}.`;
      }
      await speakText(speech);
    } catch (e) {
      setError((e as Error).message ?? "Compliance check failed");
    } finally {
      setIsProcessing(false);
    }
  }, [userApiKey, onVerdict]);

  const startListening = useCallback(async () => {
    setError(null);
    setTranscript("");

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access denied");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    const recorder = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: mimeType });
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;

      setIsProcessing(true);
      try {
        const text = await transcribeAudio(blob);
        setTranscript(text);
        await runComplianceCheck(text);
      } catch (e) {
        setError((e as Error).message ?? "Transcription failed");
        setIsProcessing(false);
      }
    };

    recorder.start(250); // collect in 250ms chunks
    setIsListening(true);
  }, [runComplianceCheck]);

  const stopListening = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsListening(false);
  }, []);

  return {
    isListening,
    isProcessing,
    transcript,
    error,
    startListening,
    stopListening,
  };
}
