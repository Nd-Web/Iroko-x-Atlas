"""
services/azure_realtime.py — Azure OpenAI Realtime API (gpt-realtime family).

Replaces AethexAI for text-to-speech and for minting the ephemeral client
secrets the browser uses to open a WebRTC call directly against Azure for
the full conversational widget. Speech-to-text lives in azure_openai.py
instead (the Whisper deployment).

GA endpoints (confirmed against Microsoft Learn — this API recently moved off
the older `/openai/realtimeapi/sessions` preview surface):

  Server-side plain WebSocket (used here for one-shot TTS):
    wss://{resource}.openai.azure.com/openai/v1/realtime?model={deployment}
    header: api-key: <key>

  Browser WebRTC ephemeral token:
    POST https://{resource}.openai.azure.com/openai/v1/realtime/client_secrets
    header: api-key: <key>

  Browser SDP exchange (done directly by the browser, not this service):
    POST https://{resource}.openai.azure.com/openai/v1/realtime/calls
    header: Authorization: Bearer <ephemeral client_secret>

Config (env):
  AZURE_OPENAI_REALTIME_ENDPOINT    e.g. https://your-resource.openai.azure.com
  AZURE_OPENAI_REALTIME_API_KEY
  AZURE_OPENAI_REALTIME_DEPLOYMENT  default gpt-realtime-2.1
  AZURE_OPENAI_REALTIME_VOICE       default marin (no Nigerian-accented preset
                                     voice exists on Azure Realtime)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import urllib.error
import urllib.request

import websockets

logger = logging.getLogger(__name__)

ENDPOINT = os.getenv("AZURE_OPENAI_REALTIME_ENDPOINT", "").rstrip("/")
API_KEY = os.getenv("AZURE_OPENAI_REALTIME_API_KEY", "")
DEPLOYMENT = os.getenv("AZURE_OPENAI_REALTIME_DEPLOYMENT", "gpt-realtime-2.1")
DEFAULT_VOICE = os.getenv("AZURE_OPENAI_REALTIME_VOICE", "marin")

_SAMPLE_RATE = 24000  # PCM16 mono, fixed by the Realtime API's audio/pcm format

# gpt-realtime is a conversational model: given text with no instructions it
# REPLIES to it ("Got it, no-go it is. If you want, I can help you…") instead of
# reading it out. These instructions pin it to plain speech synthesis.
_TTS_INSTRUCTIONS = (
    "You are a text-to-speech engine. Read the user's message aloud EXACTLY as written, "
    "word for word. Never reply to it, comment on it, summarise it, greet, or add anything."
)

# The spoken compliance persona — carried over from the AethexAI agent this
# replaced. Without it the session falls back to Azure's stock "helpful
# assistant" and behaves like a general-purpose voice bot.
IROKO_VOICE_INSTRUCTIONS = """You are the voice of Iroko AI, a regulatory-intelligence assistant for Nigerian telecom operators such as MTN Nigeria.

Your PRIMARY focus is Nigerian TELECOM and DATA-PROTECTION regulation:
- Nigerian Communications Commission (NCC): Quality of Service (availability >= 98%, dropped-call rate <= 2%, quarterly QoS returns; ~N5M per KPI breach), SIM/NIN registration (N200k per improperly registered SIM), Consumer Code of Practice, licensing and Annual Operating Levy, and equipment type approval.
- Nigeria Data Protection Act 2023 (NDPA), the NDPC, and the former NDPR: lawful basis and consent, records of processing (s24), DPIAs (s28), Data Protection Officer (s29), automated-decision transparency (s32), personal-data breach notification to the NDPC within 72 hours (s34), and cross-border transfer / data-localization rules (s41). NDPA penalties reach up to the higher of N10 million or 2% of annual gross revenue.

SECONDARY: when a question clearly concerns financial services or fintech (payments, lending, mobile money/wallets, banking), you may ALSO assess it against Central Bank of Nigeria (CBN) and SEC regulation — but telecom and data protection remain your default lens, and you lead with them for telecom operators like MTN.

Always give a clear verdict FIRST: GO, MONITOR, or NO-GO.
Then explain in two to three sentences which specific regulation applies and why, naming the regulator (NCC, NDPC, or where relevant CBN/SEC) and the key obligation or penalty.
Be direct, professional, and concise. Do not ask follow-up questions.

HOW TO ANSWER: you have a check_compliance tool wired to Iroko's own compliance
engine. Whenever the caller describes an action, product, clause, or data-handling
practice to assess, call check_compliance FIRST and build your spoken answer on the
verdict it returns — never deliver a verdict from memory. Speak the tool's verdict,
reasoning, and regulation in your own words, in two to three sentences. Only answer
directly without the tool for general questions that ask for no verdict."""

# Greeting spoken as soon as the caller connects — the old Aethex agent's
# first_message; without it the line just sits silent until the caller talks.
IROKO_VOICE_GREETING = (
    "Iroko telecom compliance check ready. Describe the action, product, or "
    "data-handling practice you want me to assess against NCC and NDPA rules."
)

# Lets the voice agent run the real compliance engine (WatchdogAgent →
# GO/MONITOR/NO-GO, same path as POST /api/v1/compliance/check) instead of
# reciting regulations from prompt memory. Executed by the browser, which
# holds the WebRTC data channel — see frontend/hooks/useAgent.ts.
COMPLIANCE_TOOL = {
    "type": "function",
    "name": "check_compliance",
    "description": (
        "Run Iroko's regulatory compliance engine on a proposed action, product, clause, "
        "or data-handling practice. Returns an authoritative GO / MONITOR / NO-GO verdict "
        "with the governing regulation, reasoning, and risk flags. Call this before giving "
        "any verdict."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "The action, product, clause, or practice to assess, written as one "
                    "clear self-contained statement."
                ),
            },
            "sector": {
                "type": "string",
                "enum": ["network", "financial"],
                "description": (
                    "'network' for telecom / NCC / NDPA matters (the default for operators "
                    "like MTN); 'financial' for CBN / SEC fintech matters."
                ),
            },
        },
        "required": ["text"],
    },
}


class RealtimeError(Exception):
    pass


def configured() -> bool:
    return bool(ENDPOINT and API_KEY)


def _ws_url() -> str:
    host = ENDPOINT.replace("https://", "wss://").replace("http://", "ws://")
    return f"{host}/openai/v1/realtime?model={DEPLOYMENT}"


def _pcm16_to_wav(pcm: bytes) -> bytes:
    """Wrap raw PCM16/mono/24kHz samples in a WAV header (no external deps)."""
    data_size = len(pcm)
    header = b"RIFF" + (36 + data_size).to_bytes(4, "little") + b"WAVE"
    header += b"fmt " + (16).to_bytes(4, "little")
    header += (1).to_bytes(2, "little")            # PCM
    header += (1).to_bytes(2, "little")            # mono
    header += _SAMPLE_RATE.to_bytes(4, "little")
    header += (_SAMPLE_RATE * 2).to_bytes(4, "little")  # byte rate
    header += (2).to_bytes(2, "little")             # block align
    header += (16).to_bytes(2, "little")            # bits per sample
    header += b"data" + data_size.to_bytes(4, "little")
    return header + pcm


def _wav_to_mp3(wav: bytes) -> bytes:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-f", "mp3", "-codec:a", "libmp3lame", "-b:a", "128k", "pipe:1"],
            input=wav, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError:
        raise RealtimeError("ffmpeg is not installed on the server — cannot encode the voice.")
    except subprocess.CalledProcessError as e:
        raise RealtimeError(f"Audio encoding failed: {e.stderr.decode()[:150]}")
    return proc.stdout


async def _connect():
    if not configured():
        raise RealtimeError(
            "Azure Realtime is not configured (set AZURE_OPENAI_REALTIME_ENDPOINT / "
            "AZURE_OPENAI_REALTIME_API_KEY)."
        )
    return websockets.connect(_ws_url(), additional_headers={"api-key": API_KEY})


# ── Text → speech ─────────────────────────────────────────────────────────────

async def _synthesize_pcm(text: str, voice: str) -> bytes:
    audio = bytearray()
    async with await _connect() as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "instructions": _TTS_INSTRUCTIONS,
                "output_modalities": ["audio"],
                "audio": {
                    "output": {
                        "voice": voice,
                        "format": {"type": "audio/pcm", "rate": _SAMPLE_RATE},
                    },
                },
            },
        }))
        await ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }))
        await ws.send(json.dumps({"type": "response.create"}))

        async for raw in ws:
            event = json.loads(raw)
            etype = event.get("type")
            if etype == "response.output_audio.delta":
                audio.extend(base64.b64decode(event["delta"]))
            elif etype == "response.done":
                break
            elif etype == "error":
                raise RealtimeError(event.get("error", {}).get("message", "Realtime API error"))
    return bytes(audio)


def synthesize_speech_mp3(text: str, voice: str | None = None) -> bytes:
    """Text -> mp3 bytes, via the Azure Realtime model. Blocking (runs its own
    event loop) so it can be called with `asyncio.to_thread` like the old
    Aethex TTS call was."""
    import asyncio
    pcm = asyncio.run(_synthesize_pcm(text, voice or DEFAULT_VOICE))
    if not pcm:
        raise RealtimeError("Realtime API returned no audio")
    return _wav_to_mp3(_pcm16_to_wav(pcm))


# Speech-to-text lives in services/azure_openai.transcribe_audio (the Whisper
# deployment) — a plain REST call is simpler than driving a realtime session.


# ── WebRTC ephemeral session (for the browser conversational widget) ──────────

def mint_webrtc_client_secret(instructions: str = "", voice: str | None = None) -> dict:
    """Mint a short-lived client_secret the browser can use to open a WebRTC
    call directly against Azure. Safe to hand to the browser (unlike the real
    api-key), per the GA client_secrets flow."""
    if not configured():
        raise RealtimeError(
            "Azure Realtime is not configured (set AZURE_OPENAI_REALTIME_ENDPOINT / "
            "AZURE_OPENAI_REALTIME_API_KEY)."
        )
    session: dict = {
        "session": {
            "type": "realtime",
            "model": DEPLOYMENT,
            "instructions": instructions or IROKO_VOICE_INSTRUCTIONS,
            "tools": [COMPLIANCE_TOOL],
            "tool_choice": "auto",
            "audio": {"output": {"voice": voice or DEFAULT_VOICE}},
        },
    }

    req = urllib.request.Request(
        f"{ENDPOINT}/openai/v1/realtime/client_secrets",
        data=json.dumps(session).encode(),
        method="POST",
        headers={"api-key": API_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RealtimeError(f"client_secrets {e.code}: {e.read().decode()[:200]}") from e

    client_secret = data.get("value", "")
    if not client_secret:
        raise RealtimeError("No client_secret in Azure response")
    return {
        "client_secret": client_secret,
        "calls_url": f"{ENDPOINT}/openai/v1/realtime/calls",
        "greeting": IROKO_VOICE_GREETING,
    }
