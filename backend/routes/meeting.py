"""
Meeting Route — send Iroko into a live meeting and let it answer aloud.

  POST /api/meeting/join    {meeting_url}          → bot joins + greets
  GET  /api/meeting/status/{bot_id}                → join status
  POST /api/meeting/ask     {bot_id, question}     → Iroko answers aloud in the meeting
  POST /api/meeting/leave   {bot_id}               → bot leaves

Answers come from the same multi-agent brain as the chat (StrategistAgent),
condensed to a few spoken sentences, then voiced via Aethex and played into
the meeting by the Recall bot.
"""
import asyncio
import json
import logging
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from models.database import get_db, User
from services.auth_utils import get_current_user
from services import meeting_service as ms

router = APIRouter(prefix="/api/meeting", tags=["Meeting"])
logger = logging.getLogger(__name__)

# ── Live-listening state (in-memory, per bot) ─────────────────────────────────
# Iroko auto-answers questions it hears. These guards stop it from talking over
# itself, answering its own voice back, or firing on every stray sentence.
_answering: dict[str, float] = {}    # bot_id -> monotonic ts it started answering
_last_answer: dict[str, float] = {}  # bot_id -> monotonic ts it last finished
_BUSY_TIMEOUT = 45.0                  # force-clear a stuck "busy" after this long
_COOLDOWN = 6.0                       # min gap between answers, seconds

_Q_STARTS = (
    "can ", "could ", "is ", "are ", "do ", "does ", "did ", "should ", "would ",
    "will ", "what", "how", "why", "when", "where", "which", "who", "whats",
    "what's", "may ", "shall ",
)
_Q_PHRASES = (
    "can we", "can i", "should we", "are we", "is it", "do we", "does the",
    "what is", "what are", "how do", "how can", "how much", "why is", "can iroko",
    "is there", "are there", "do i", "is our", "are our",
)


def _looks_like_question(text: str) -> bool:
    """Permissive question detector — live captions often lack a '?'."""
    t = text.strip().lower()
    if len(t) < 12 or len(t.split()) < 4:
        return False
    if "?" in t:
        return True
    return t.startswith(_Q_STARTS) or any(p in t for p in _Q_PHRASES)


class JoinRequest(BaseModel):
    meeting_url: str = Field(..., min_length=8, max_length=2000)


class AskRequest(BaseModel):
    bot_id: str
    question: str = Field(..., min_length=2, max_length=2000)


class LeaveRequest(BaseModel):
    bot_id: str


def _speechify(text: str) -> str:
    """Strip markdown, keep it to a few spoken sentences."""
    text = re.sub(r"[*_#`>|]", "", text or "")
    text = re.sub(r"\s*\n+\s*", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    out, n = [], 0
    for p in parts:
        out.append(p)
        n += len(p)
        if len(out) >= 4 or n > 600:
            break
    return " ".join(out)


async def _brain_answer(question: str) -> str:
    """Run the full Iroko multi-agent brain, condensed to a spoken reply."""
    from agents.strategist import StrategistAgent
    strategist = StrategistAgent()
    wrapped = ("Answer in 2 to 4 short spoken sentences for a live meeting — "
               "plain, lead with the key point: " + question)
    result = json.loads(await strategist.investigate(question=wrapped))
    return _speechify(result.get("answer", "")) or "I don't have enough information to answer that."


async def _answer_in_meeting(bot_id: str, question: str) -> None:
    """Background: answer a question Iroko overheard and speak it into the call."""
    try:
        answer = await _brain_answer(question)
        await asyncio.to_thread(ms.speak, bot_id, answer)  # speak is blocking (ffmpeg + HTTP)
        logger.info(f"[meeting {bot_id}] auto-answered: {question[:60]!r}")
    except Exception:
        logger.exception(f"[meeting {bot_id}] auto-answer failed")
    finally:
        _answering.pop(bot_id, None)
        _last_answer[bot_id] = time.monotonic()


@router.get("/config")
async def meeting_config(current_user: User = Depends(get_current_user)):
    """Tell the UI whether the meeting feature is switched on, and if not, which keys are missing."""
    return ms.config_status()


@router.post("/join")
async def join(body: JoinRequest, current_user: User = Depends(get_current_user)):
    try:
        res = ms.join_meeting(body.meeting_url.strip())
    except ms.MeetingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ms.greet(res["bot_id"])  # best-effort spoken greeting once it's in
    return res


@router.get("/status/{bot_id}")
async def status(bot_id: str, current_user: User = Depends(get_current_user)):
    try:
        return {"status": ms.bot_status(bot_id)}
    except ms.MeetingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ask")
async def ask(body: AskRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """Answer the question with the full Iroko brain and speak it into the meeting."""
    try:
        answer = await _brain_answer(body.question)
        await asyncio.to_thread(ms.speak, body.bot_id, answer)
    except ms.MeetingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Meeting ask failed")
        raise HTTPException(status_code=500, detail=f"Could not answer in the meeting: {e}")
    return {"answer": answer}


@router.post("/webhook")
async def webhook(request: Request):
    """Recall streams live transcripts here. When Iroko overhears a question,
    it answers aloud automatically. No auth — Recall calls this, not the browser.

    Guards: only final utterances, only question-like text, never its own voice,
    a busy-lock so it won't talk over itself, and a short cooldown between answers.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}

    if payload.get("event") != "transcript.data":
        return {"ok": True}

    outer = payload.get("data") or {}
    inner = outer.get("data") or {}
    bot_id = (outer.get("bot") or {}).get("id")
    words = inner.get("words") or []
    text = " ".join(w.get("text", "") for w in words).strip()
    speaker = ((inner.get("participant") or {}).get("name") or "").strip()

    if not bot_id or not text:
        return {"ok": True}
    if speaker.lower().startswith("iroko"):   # ignore Iroko's own voice → no feedback loop
        return {"ok": True}
    if not _looks_like_question(text):
        return {"ok": True}

    now = time.monotonic()
    busy_since = _answering.get(bot_id)
    if busy_since and (now - busy_since) < _BUSY_TIMEOUT:
        return {"ok": True}                    # already answering — don't overlap
    if (now - _last_answer.get(bot_id, 0.0)) < _COOLDOWN:
        return {"ok": True}                    # just answered — brief pause

    _answering[bot_id] = now
    asyncio.create_task(_answer_in_meeting(bot_id, text))  # answer async; ACK Recall fast
    return {"ok": True}


@router.post("/leave")
async def leave(body: LeaveRequest, current_user: User = Depends(get_current_user)):
    ms.leave_meeting(body.bot_id)
    _answering.pop(body.bot_id, None)
    _last_answer.pop(body.bot_id, None)
    return {"left": True}
