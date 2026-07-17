"""
services/meeting_service.py — send Iroko into a live meeting (via Recall.ai)
and make it speak, from the app itself.

Powers the "Iroko, join my meeting" panel: a meeting URL comes in, an
"Iroko AI" bot joins (Teams / Zoom / Meet), greets the room, and then
speaks answers on demand in the Nigerian voice.

Pipeline for speaking: text → Aethex TTS (WAV) → ffmpeg (mp3, the only
format Recall's output_audio accepts) → Recall output_audio.

Config (env):
  RECALL_API_KEY   *required* to enable the feature
  RECALL_REGION    default us-west-2
  AETHEX_API_KEY   (or IROKO_AGENT_API_KEY) — the voice
  MEETING_VOICE_ID default Ada (Nigerian English)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

RECALL_REGION = os.getenv("RECALL_REGION", "us-west-2")
RECALL_BASE = f"https://{RECALL_REGION}.recall.ai/api/v1"
RECALL_KEY = os.getenv("RECALL_API_KEY", "")
AETHEX_KEY = os.getenv("AETHEX_API_KEY") or os.getenv("IROKO_AGENT_API_KEY", "")
VOICE_ID = os.getenv("MEETING_VOICE_ID", "354d8730-388b-5d94-a7e8-9f8bc87dc4fc")

GREETING = ("Hello, this is Iroko AI. I have joined the meeting and I'm ready to "
            "answer your telecom and compliance questions.")


class MeetingError(Exception):
    pass


def configured() -> bool:
    return bool(RECALL_KEY and AETHEX_KEY)


def config_status() -> dict:
    """Report which keys are present so the UI can name what's missing."""
    missing = []
    if not RECALL_KEY:
        missing.append("RECALL_API_KEY")
    if not AETHEX_KEY:
        missing.append("AETHEX_API_KEY")
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


# ── Voice: Aethex TTS → mp3 ───────────────────────────────────────────────────

def _tts_mp3_b64(text: str) -> str:
    r = urllib.request.Request(
        "https://api.aethexai.com/api/v1/tts",
        data=json.dumps({"text": text, "voice_id": VOICE_ID}).encode(),
        method="POST",
        headers={"X-API-Key": AETHEX_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=90) as resp:
        wav = resp.read()
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-f", "mp3", "-codec:a", "libmp3lame", "-b:a", "128k", "pipe:1"],
            input=wav, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError:
        raise MeetingError("ffmpeg is not installed on the server — cannot encode the voice.")
    except subprocess.CalledProcessError as e:
        raise MeetingError(f"Audio encoding failed: {e.stderr.decode()[:150]}")
    return base64.b64encode(proc.stdout).decode()


# ── Public API ────────────────────────────────────────────────────────────────

def join_meeting(meeting_url: str) -> dict:
    """Create an 'Iroko AI' bot that joins the meeting. Returns {bot_id, platform}."""
    if not configured():
        raise MeetingError("Meeting integration is not configured (set RECALL_API_KEY).")
    bot = _recall("POST", "/bot/", {"meeting_url": meeting_url, "bot_name": "Iroko AI"})
    return {"bot_id": bot["id"], "platform": (bot.get("meeting_url") or {}).get("platform", "")}


def bot_status(bot_id: str) -> str:
    b = _recall("GET", f"/bot/{bot_id}/")
    codes = [s.get("code") for s in b.get("status_changes", [])]
    return codes[-1] if codes else "unknown"


def speak(bot_id: str, text: str) -> None:
    """Make the bot say `text` out loud in the meeting."""
    if not text:
        return
    b64 = _tts_mp3_b64(text)
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
