"""
services/gpt_live.py — GPT-Live (gpt-live-1) for the browser voice widget.

GPT-Live is a full-duplex voice model with its own API (not the Realtime API).
The browser makes a WebRTC offer; this server creates the live session with the
API key, which never reaches the browser, and returns Azure's SDP answer:

  POST {endpoint}/openai/v1/live/sessions
  {"session": {...}, "transport": {"type": "webrtc", "sdp": "<offer>"}}
  -> 201 {"session": {"id": ...}, "transport": {"type": "webrtc", "sdp": "<answer>"}}

Compliance checks use client delegation: GPT-Live hands the task to the browser
(session.delegation.created), which runs Iroko's compliance engine and returns
the verdict as commentary for the agent to speak. See frontend/hooks/useAgent.ts.

Config (env): GPT_LIVE_ENDPOINT, GPT_LIVE_API_KEY, GPT_LIVE_DEPLOYMENT (gpt-live-1),
GPT_LIVE_VOICE (marin).
Docs: https://learn.microsoft.com/azure/foundry/openai/how-to/gpt-live
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from services.azure_realtime import IROKO_VOICE_GREETING, IROKO_VOICE_INSTRUCTIONS

_MAX_SDP = 20000

# The Realtime persona says "call check_compliance". GPT-Live has no tools of its
# own here: it delegates, and the browser answers the delegation.
_HOW_TO_ANSWER = """HOW TO ANSWER: Iroko's own compliance engine is available to you through
delegation. Whenever the caller describes an action, product, clause, or data-handling
practice to assess, delegate the assessment and briefly tell the caller you are checking
it. Never deliver a verdict from memory. When the result arrives, speak its verdict,
regulation, and reasoning in your own words, in two to three sentences, naming the
source document when one is given. If the result says Iroko could not verify the
action, say exactly that and that compliance should confirm it; do not replace it
with a verdict of your own. Only answer directly, without delegating, for general
questions that ask for no verdict."""

LIVE_INSTRUCTIONS = IROKO_VOICE_INSTRUCTIONS.split("HOW TO ANSWER:", 1)[0].rstrip() + "\n\n" + _HOW_TO_ANSWER


class LiveError(Exception):
    pass


def _config() -> tuple[str, str, str, str]:
    return (
        os.getenv("GPT_LIVE_ENDPOINT", "").rstrip("/"),
        os.getenv("GPT_LIVE_API_KEY", ""),
        os.getenv("GPT_LIVE_DEPLOYMENT", "gpt-live-1"),
        os.getenv("GPT_LIVE_VOICE", "marin"),
    )


def configured() -> bool:
    endpoint, key, _deployment, _voice = _config()
    return bool(endpoint and key)


async def create_webrtc_session(sdp: str, instructions: str = "", voice: str | None = None) -> dict:
    """Create a GPT-Live WebRTC session for the browser's offer; return Azure's answer."""
    endpoint, key, deployment, default_voice = _config()
    if not (endpoint and key):
        raise LiveError("Voice agent is not configured (set GPT_LIVE_ENDPOINT and GPT_LIVE_API_KEY).")
    if not isinstance(sdp, str) or not sdp.startswith("v=0") or len(sdp) > _MAX_SDP:
        raise ValueError("Invalid WebRTC offer")
    body = {
        "session": {
            "model": deployment,
            "instructions": instructions or LIVE_INSTRUCTIONS,
            "audio": {"output": {"voice": voice or default_voice}},
            "delegation": {"type": "client"},
        },
        "transport": {"type": "webrtc", "sdp": sdp},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{endpoint}/openai/v1/live/sessions", json=body,
                                         headers={"api-key": key})
    except httpx.RequestError as exc:
        # Name the host, never the key: an unreachable or deleted resource is the usual cause.
        raise LiveError(f"Cannot reach the voice service at {urlparse(endpoint).hostname} "
                        f"({type(exc).__name__}).") from exc
    if response.status_code not in (200, 201):
        raise LiveError(f"Voice session was refused ({response.status_code}): {response.text[:200]}")
    data = response.json()
    answer = (data.get("transport") or {}).get("sdp")
    if not answer:
        raise LiveError("The voice service returned no connection answer.")
    return {"sdp": answer, "session_id": (data.get("session") or {}).get("id"), "greeting": IROKO_VOICE_GREETING}
