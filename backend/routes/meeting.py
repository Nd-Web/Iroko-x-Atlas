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
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models.database import get_db, User
from services.auth_utils import get_current_user
from services import meeting_service as ms

router = APIRouter(prefix="/api/meeting", tags=["Meeting"])
logger = logging.getLogger(__name__)


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


@router.get("/config")
async def meeting_config(current_user: User = Depends(get_current_user)):
    """Tell the UI whether the meeting feature is switched on (RECALL_API_KEY set)."""
    return {"enabled": ms.configured()}


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
    from agents.strategist import StrategistAgent
    try:
        strategist = StrategistAgent()
        wrapped = ("Answer in 2 to 4 short spoken sentences for a live meeting — "
                   "plain, lead with the key point: " + body.question)
        result = json.loads(await strategist.investigate(question=wrapped))
        answer = _speechify(result.get("answer", "")) or "I don't have enough information to answer that."
        ms.speak(body.bot_id, answer)
    except ms.MeetingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Meeting ask failed")
        raise HTTPException(status_code=500, detail=f"Could not answer in the meeting: {e}")
    return {"answer": answer}


@router.post("/leave")
async def leave(body: LeaveRequest, current_user: User = Depends(get_current_user)):
    ms.leave_meeting(body.bot_id)
    return {"left": True}
