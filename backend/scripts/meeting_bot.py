"""
Iroko AI — Teams / Zoom / Meet meeting bot bridge (via Recall.ai).

Sends an "Iroko AI" bot into a meeting, then makes Iroko answer questions
*out loud in the meeting* in its Nigerian voice. Two ways to drive it:

  • MANUAL (reliable, presenter-controlled): type the question in this
    terminal → Iroko answers aloud in the meeting. Best for the live demo.
  • AUTO (--auto, experimental): the bot transcribes the meeting and answers
    on its own when it hears "Iroko, …?".

Pipeline:  Recall bot (in the meeting)  →  your question  →  Iroko backend
(/api/atlas/ask, grounded answer)  →  Iroko backend /api/voice/tts
(Azure OpenAI Realtime → mp3)  →  Recall output_audio  →  the bot speaks it
in the meeting.

Run (from the backend directory):
    RECALL_API_KEY=xxx MEETING_URL="https://teams.live.com/meet/..." \
      python -m scripts.meeting_bot
  or:  python -m scripts.meeting_bot --meeting "https://teams.live.com/meet/..."

Config via env (all have sensible defaults except the two marked *required*):
  RECALL_API_KEY   *required*   Recall.ai API key
  MEETING_URL      *required*   the Teams/Zoom/Meet join link (or --meeting)
  RECALL_REGION    default us-west-2
  IROKO_BASE       default https://iroko-x-atlas.onrender.com
  IROKO_EMAIL      default admin@mtn.ng
  IROKO_PASSWORD   default AtlasAdmin2026!
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────

REGION = os.getenv("RECALL_REGION", "us-west-2")
RECALL_BASE = f"https://{REGION}.recall.ai/api/v1"
RECALL_KEY = os.getenv("RECALL_API_KEY", "")
IROKO_BASE = os.getenv("IROKO_BASE", "https://iroko-x-atlas.onrender.com").rstrip("/")
IROKO_EMAIL = os.getenv("IROKO_EMAIL", "admin@mtn.ng")
IROKO_PASSWORD = os.getenv("IROKO_PASSWORD", "AtlasAdmin2026!")

_TOKEN = ""  # set in main() after login; tts_mp3_b64() speaks through the Iroko backend

GREETING = ("Hello, this is Iroko AI. I have joined the meeting and I'm ready to "
            "answer your telecom and compliance questions.")
FILLER = "One moment — let me check that."


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _req(url: str, method: str, headers: dict, body=None, raw_response=False, timeout=90):
    data = None
    if body is not None:
        # bytes → send as-is; dict/list → JSON-encode. (raw_response is separate.)
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        content = resp.read()
        if raw_response:
            return content
        ctype = resp.headers.get("Content-Type", "")
        return json.loads(content) if content and "json" in ctype else content


def recall(method: str, path: str, body=None):
    return _req(RECALL_BASE + path, method,
                {"Authorization": f"Token {RECALL_KEY}", "Content-Type": "application/json"},
                body)


# ── Iroko backend ─────────────────────────────────────────────────────────────

def iroko_login() -> str:
    d = _req(f"{IROKO_BASE}/api/auth/login", "POST",
             {"Content-Type": "application/json"},
             {"email": IROKO_EMAIL, "password": IROKO_PASSWORD})
    return d["access_token"]


def iroko_ask(token: str, question: str, _retry: bool = True) -> str:
    """Ask Iroko and return a concise, speech-friendly answer.

    Self-heals a 401: the free-tier backend can cold-start and rotate its
    SECRET_KEY mid-session, invalidating the token — so on 401 we re-login
    once and retry with a fresh token.
    """
    wrapped = ("Answer in 2 to 4 short spoken sentences for a live meeting — "
               "plain, no markdown, lead with the key point: " + question)
    try:
        d = _req(f"{IROKO_BASE}/api/atlas/ask", "POST",
                 {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                 {"query": wrapped}, timeout=120)
        ans = (d.get("answer") or "").strip()
    except urllib.error.HTTPError as e:
        if e.code == 401 and _retry:
            return iroko_ask(iroko_login(), question, _retry=False)
        return f"Sorry, I couldn't reach the knowledge base just now. HTTP {e.code}."
    except Exception as e:
        return f"Sorry, I couldn't reach the knowledge base just now. {e}"
    return _speechify(ans)


def _speechify(text: str) -> str:
    """Strip markdown and cap to a few sentences so the spoken answer stays tight."""
    text = re.sub(r"[*_#`>|]", "", text)
    text = re.sub(r"\s*\n+\s*", " ", text).strip()
    # keep first ~4 sentences / 600 chars
    parts = re.split(r"(?<=[.!?])\s+", text)
    out, n = [], 0
    for p in parts:
        out.append(p)
        n += len(p)
        if len(out) >= 4 or n > 600:
            break
    return " ".join(out)


# ── Voice: Iroko backend TTS (Azure Realtime) → mp3 → the bot speaks ──────────

def tts_mp3_b64(text: str, _retry: bool = True) -> str:
    """mp3 already comes back from the backend — just base64 it for Recall."""
    global _TOKEN
    try:
        mp3 = _req(f"{IROKO_BASE}/api/voice/tts", "POST",
                   {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"},
                   {"text": text}, raw_response=True, timeout=90)
    except urllib.error.HTTPError as e:
        if e.code == 401 and _retry:
            _TOKEN = iroko_login()
            return tts_mp3_b64(text, _retry=False)
        raise
    return base64.b64encode(mp3).decode()


def speak(bot_id: str, text: str) -> None:
    if not text:
        return
    b64 = tts_mp3_b64(text)
    recall("POST", f"/bot/{bot_id}/output_audio/", {"kind": "mp3", "b64_data": b64})


# ── Bot lifecycle ─────────────────────────────────────────────────────────────

def create_bot(meeting_url: str, transcribe: bool) -> str:
    payload = {"meeting_url": meeting_url, "bot_name": "Iroko AI"}
    if transcribe:
        payload["recording_config"] = {"transcript": {"provider": {"meeting_captions": {}}}}
    bot = recall("POST", "/bot/", payload)
    return bot["id"]


def bot_status(bot_id: str) -> str:
    b = recall("GET", f"/bot/{bot_id}/")
    codes = [s.get("code") for s in b.get("status_changes", [])]
    return codes[-1] if codes else "?"


def wait_in_call(bot_id: str, timeout=90) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = bot_status(bot_id)
        if st == "in_call_recording":
            return True
        if st in ("call_ended", "fatal", "done", "processing"):
            return False
        time.sleep(3)
    return False


def leave(bot_id: str) -> None:
    try:
        recall("POST", f"/bot/{bot_id}/leave_call/", {})
    except Exception:
        pass


# ── Auto mode: transcript polling ─────────────────────────────────────────────

WAKE = re.compile(r"\biroko\b", re.IGNORECASE)


def transcript_text(bot_id: str) -> list[str]:
    """Return the list of final utterances seen so far (best-effort across API shapes)."""
    try:
        d = recall("GET", f"/bot/{bot_id}/transcript/")
    except Exception:
        return []
    utts = []
    items = d if isinstance(d, list) else d.get("results", d.get("transcript", []))
    for seg in items or []:
        words = seg.get("words") or []
        txt = seg.get("text") or " ".join(w.get("text", "") for w in words)
        if txt.strip():
            utts.append(txt.strip())
    return utts


def auto_loop(bot_id: str, token: str, stop: threading.Event):
    seen = set()
    while not stop.is_set():
        for utt in transcript_text(bot_id):
            key = utt.lower()
            if key in seen:
                continue
            seen.add(key)
            if WAKE.search(utt) and ("?" in utt or len(utt.split()) >= 4):
                q = WAKE.sub("", utt).strip(" ,.?") + "?"
                print(f"\n[heard] {utt}\n[answering…]")
                _answer(bot_id, token, q)
        time.sleep(2.5)


# ── Answering ─────────────────────────────────────────────────────────────────

def _pr(msg: str):
    """Console print that never crashes on a non-UTF-8 terminal (Windows cp1252)."""
    try:
        print(msg)
    except Exception:
        print(msg.encode("ascii", "replace").decode())


def _answer(bot_id: str, token: str, question: str):
    try:
        speak(bot_id, FILLER)  # instant acknowledgement covers the think time
    except Exception:
        pass
    ans = iroko_ask(token, question)
    # Speak FIRST — the spoken answer must never depend on console printing.
    try:
        speak(bot_id, ans)
    except Exception as e:
        _pr(f"[speak failed] {e}")
    _pr(f"[Iroko] {ans}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Make stdout tolerant of Unicode (₦, en-dashes, …) on a Windows console.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", default=os.getenv("MEETING_URL", ""))
    ap.add_argument("--auto", action="store_true", help="auto-answer from live transcript")
    ap.add_argument("--no-greeting", action="store_true")
    args = ap.parse_args()

    global _TOKEN

    if not RECALL_KEY:
        sys.exit("Set RECALL_API_KEY.")
    if not args.meeting:
        sys.exit("Set MEETING_URL or pass --meeting.")

    print(f"Logging in to Iroko ({IROKO_BASE})…")
    token = iroko_login()
    _TOKEN = token
    print("Sending 'Iroko AI' into the meeting…")
    bot_id = create_bot(args.meeting, transcribe=args.auto)
    print(f"  bot id: {bot_id}")
    print("  waiting to join (admit it from the lobby if prompted)…")
    if not wait_in_call(bot_id, 90):
        print("  Bot did not reach the call. Check the lobby / meeting link.")
    else:
        print("  ✓ Iroko is in the meeting.")
        if not args.no_greeting:
            try:
                speak(bot_id, GREETING)
            except Exception as e:
                print(f"  (greeting failed: {e})")

    stop = threading.Event()
    if args.auto:
        threading.Thread(target=auto_loop, args=(bot_id, token, stop), daemon=True).start()
        print("\nAUTO mode on — Iroko will answer when it hears 'Iroko, …?'.")

    print("\nType a question and press Enter — Iroko answers it aloud in the meeting.")
    print("Commands:  /quit  → leave the meeting and exit.\n")
    try:
        while True:
            line = input("question> ").strip()
            if not line:
                continue
            if line in ("/quit", "/q", "/exit"):
                break
            _answer(bot_id, token, line)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        print("\nLeaving the meeting…")
        leave(bot_id)
        print("Done. Iroko has left the meeting.")


if __name__ == "__main__":
    main()
