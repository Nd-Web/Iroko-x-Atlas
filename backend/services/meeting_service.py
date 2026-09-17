"""
services/meeting_service.py — send Iroko into a live meeting (via Recall.ai)
and make it speak, from the app itself.

Powers the "Iroko, join my meeting" panel: a meeting URL comes in, an
"Iroko AI" bot joins (Teams / Zoom / Meet), greets the room, and then
speaks answers on demand.

Pipeline for speaking: text → Azure Realtime TTS (PCM/WAV) → ffmpeg (mp3, the
only format Recall's output_audio accepts) → Recall output_audio.

Config (env):
  RECALL_API_KEY   *required* to enable the feature
  RECALL_REGION    default us-west-2
  Azure Realtime — see services/azure_realtime.py (AZURE_OPENAI_REALTIME_*)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request

from services import azure_realtime

logger = logging.getLogger(__name__)

RECALL_REGION = os.getenv("RECALL_REGION", "us-west-2")
RECALL_BASE = f"https://{RECALL_REGION}.recall.ai/api/v1"
RECALL_KEY = os.getenv("RECALL_API_KEY", "")

GREETING = ("Hello, this is Iroko AI. I have joined the meeting and I'm ready to "
            "answer your telecom and compliance questions.")


class MeetingError(Exception):
    pass


def configured() -> bool:
    return bool(RECALL_KEY and azure_realtime.configured())


def config_status() -> dict:
    """Report which keys are present so the UI can name what's missing."""
    missing = []
    if not RECALL_KEY:
        missing.append("RECALL_API_KEY")
    if not azure_realtime.configured():
        missing.append("AZURE_OPENAI_REALTIME_API_KEY")
    return {"enabled": not missing, "missing": missing}


# ── Recall API ────────────────────────────────────────────────────────────────

def _recall(method: str, path: str, body=None, timeout: int = 40):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        RECALL_BASE + path, data=data, method=method,
        headers={"Authorization": f"Token {RECALL_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            content = resp.read()
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        raise MeetingError(f"Recall API {e.code}: {e.read().decode()[:200]}") from e


# ── Voice: Azure Realtime TTS → mp3 ────────────────────────────────────────────

def _tts_mp3(text: str) -> bytes:
    try:
        return azure_realtime.synthesize_speech_mp3(text)
    except azure_realtime.RealtimeError as e:
        raise MeetingError(str(e)) from e


# ── Public API ────────────────────────────────────────────────────────────────

def _webhook_url() -> str:
    """Public URL Recall streams live transcripts to. The backend is directly
    reachable, so this is the backend's own origin + the webhook path."""
    base = (
        os.getenv("MEETING_WEBHOOK_BASE")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "https://iroko-x-atlas.onrender.com"
    ).rstrip("/")
    return base + "/api/meeting/webhook"


def join_meeting(meeting_url: str, listen: bool = True) -> dict:
    """Create an 'Iroko AI' bot that joins the meeting.

    When `listen` is on, the bot also transcribes the call in real time and
    streams each final utterance to our webhook, so Iroko can hear questions
    and answer aloud without anyone touching the dashboard.

    Returns {bot_id, platform, listening}.
    """
    if not configured():
        raise MeetingError("Meeting integration is not configured (set RECALL_API_KEY).")
    body: dict = {"meeting_url": meeting_url, "bot_name": "Iroko AI"}
    if listen:
        body["recording_config"] = {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_low_latency",
                        "language_code": "en",
                    }
                }
            },
            "realtime_endpoints": [
                {"type": "webhook", "url": _webhook_url(), "events": ["transcript.data"]}
            ],
        }
    bot = _recall("POST", "/bot/", body)
    return {
        "bot_id": bot["id"],
        "platform": (bot.get("meeting_url") or {}).get("platform", ""),
        "listening": listen,
    }


def bot_status(bot_id: str) -> str:
    b = _recall("GET", f"/bot/{bot_id}/")
    codes = [s.get("code") for s in b.get("status_changes", [])]
    return codes[-1] if codes else "unknown"


def speak(bot_id: str, text: str) -> None:
    """Make the bot say `text` out loud in the meeting."""
    if not text:
        return
    mp3 = _tts_mp3(text)
    b64 = base64.b64encode(mp3).decode()
    _recall("POST", f"/bot/{bot_id}/output_audio/", {"kind": "mp3", "b64_data": b64})


def greet(bot_id: str) -> None:
    try:
        speak(bot_id, GREETING)
    except Exception as e:  # greeting is best-effort
        logger.warning(f"Meeting greeting failed: {e}")


def leave_meeting(bot_id: str) -> None:
    try:
        _recall("POST", f"/bot/{bot_id}/leave_call/", {})
    except Exception as e:
        logger.warning(f"leave_call failed: {e}")
