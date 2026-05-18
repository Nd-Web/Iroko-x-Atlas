"""
routes/chat.py — Conversation management and message routing for Iroko AI.

GET    /api/chat/conversations             List conversations for current user
POST   /api/chat/conversations             Create a new conversation
GET    /api/chat/conversations/{id}        Get conversation with messages
POST   /api/chat/conversations/{id}/messages  Send message, run orchestrator
DELETE /api/chat/conversations/{id}        Delete a conversation
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import get_db, Conversation, Message
from services.auth_utils import get_current_user
from services.memory import conversation_memory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    reasoning_steps: Optional[list] = None
    risk_score: Optional[float] = None
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: Optional[str]
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    org_id: str = Field(default="MTN Nigeria")


def _fmt(dt) -> str:
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    return dt.isoformat() + ("Z" if hasattr(dt, "tzinfo") and dt.tzinfo is None else "")


def _msg_out(m) -> MessageOut:
    steps = None
    if hasattr(m, "agent_trace") and m.agent_trace:
        steps = m.agent_trace
    risk = None
    return MessageOut(
        id=str(m.id), role=str(m.role),
        content=str(m.content),
        reasoning_steps=steps,
        risk_score=risk,
        created_at=_fmt(m.created_at),
    )


def _conv_out(c, include_messages: bool = False):
    msgs = list(c.messages) if hasattr(c, "messages") else []
    base = ConversationOut(
        id=str(c.id),
        title=c.title or "Untitled",
        message_count=len(msgs),
        created_at=_fmt(c.created_at),
        updated_at=_fmt(c.updated_at),
    )
    if include_messages:
        return ConversationDetail(
            **base.model_dump(),
            messages=[_msg_out(m) for m in msgs],
        )
    return base


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
        .all()
    )
    return [_conv_out(c) for c in convs]


@router.post("/conversations", response_model=ConversationDetail)
async def create_conversation(
    body: CreateConversationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    import uuid
    conv = Conversation(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=body.title or "New Conversation",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _conv_out(conv, include_messages=True)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _conv_out(conv, include_messages=True)


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationDetail)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    import uuid

    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=body.content,
        agent_trace=[],
        citations=[],
    )
    db.add(user_msg)
    db.commit()

    # Add to in-memory conversation memory
    await conversation_memory.add_message(conversation_id, "user", body.content)

    # Run orchestrator
    assistant_content = "I'm processing your request…"
    reasoning_steps: list[dict] = []
    risk_score: float = 1.0

    try:
        from agents.orchestrator import orchestrate_pipeline

        history = await conversation_memory.get_history(conversation_id)

        async for event in orchestrate_pipeline(
            query=body.content, org_id=body.org_id
        ):
            if event.get("type") == "final":
                assistant_content = event.get("response", "")
                risk_score = float(event.get("risk_score", 1))
                reasoning_steps = event.get("reasoning_steps", [])
            elif "agent" in event:
                reasoning_steps.append(event)
    except Exception as exc:
        logger.error(f"send_message orchestrator error: {exc}", exc_info=True)
        assistant_content = "I encountered an error processing your request. Please try again."

    # Save assistant reply
    asst_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        agent_trace=reasoning_steps,
        citations=[],
    )
    db.add(asst_msg)

    # Update conversation title if it's still generic
    if conv.title in ("New Conversation", "string", None, ""):
        conv.title = body.content[:60] + ("…" if len(body.content) > 60 else "")
    conv.updated_at = datetime.now(timezone.utc)

    db.commit()

    await conversation_memory.add_message(conversation_id, "assistant", assistant_content)

    db.refresh(conv)
    return _conv_out(conv, include_messages=True)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
