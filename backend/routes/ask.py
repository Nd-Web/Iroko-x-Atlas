"""
Ask Route -- Main AI query endpoint with real SSE streaming.
"""
import asyncio
import json
import logging
import os
import tempfile

from typing import Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from models.database import get_db, User, Conversation, Message, AgentRun, AuditLog, KnowledgeGap
from models.schemas import AskRequest, AskResponse
from services.auth_utils import get_current_user
from agents.strategist import StrategistAgent

router = APIRouter(prefix="/api/atlas", tags=["Atlas AI"])
logger = logging.getLogger(__name__)

# ── Per-user DB-backed rate limiting ──────────────────────────────────────────
# 30 requests per 60-second window per user. Survives restarts / multi-worker.
_RATE_LIMIT_MAX = 30
_RATE_LIMIT_WINDOW = 60


def _check_rate_limit(user_id: str) -> bool:
    """DB-backed rate limit check. Survives restarts and works with multiple workers."""
    try:
        from models.database import SessionLocal, AgentRun, Conversation
        from sqlalchemy import func
        cutoff = datetime.utcnow() - timedelta(seconds=_RATE_LIMIT_WINDOW)
        db = SessionLocal()
        try:
            count = db.query(func.count(AgentRun.id)).filter(
                AgentRun.conversation_id.in_(
                    db.query(Conversation.id).filter(
                        Conversation.user_id == user_id
                    )
                ),
                AgentRun.agent_type == "strategist",
                AgentRun.created_at >= cutoff,
            ).scalar() or 0
            return count < _RATE_LIMIT_MAX
        finally:
            db.close()
    except Exception:
        return True  # Fail open — don't block users if rate check itself fails


# ── Starter question cache ───────────────────────────────────────────────────
# Only the suggestion-box questions (shown in the UI before the user types
# anything) are pre-computed at startup and cached for instant response.
# Every other query goes through the full AI pipeline.
STARTER_QUERIES = [
    "Why are customer complaints spiking in Lagos?",
    "Which vendor contracts are expiring soon?",
    "What is our current NCC compliance status?",
    "What are the key findings from the Q1 2026 network report?",
]

_starter_cache: dict = {}           # {normalized_query: result_str (JSON)}
_CACHE_TTL_SECONDS = 300            # 5-minute TTL — live data stays fresh


def _normalize_q(q: str) -> str:
    return q.strip().lower().rstrip("?!.").strip()


_starter_keys = {_normalize_q(q) for q in STARTER_QUERIES}


def _get_cached_starter(query: str) -> Optional[str]:
    """Return cached result_str ONLY if query matches a starter suggestion."""
    key = _normalize_q(query)
    if key not in _starter_keys:
        return None                 # not a starter → full pipeline
    entry = _starter_cache.get(key)
    if not entry:
        return None                 # not yet computed
    age = (datetime.utcnow() - entry["cached_at"]).total_seconds()
    if age > _CACHE_TTL_SECONDS:
        _starter_cache.pop(key, None)
        return None
    logger.info(f"Starter cache HIT: '{query[:60]}' (age {age:.0f}s)")
    return entry["result_str"]


async def warm_starter_cache():
    """Pre-compute answers for all starter suggestion-box queries.
    Called once at startup and can be re-called to refresh."""
    logger.info("Warming starter cache for %d suggestion-box queries...", len(STARTER_QUERIES))
    for q in STARTER_QUERIES:
        key = _normalize_q(q)
        try:
            strategist = StrategistAgent()
            result_str = await strategist.investigate(question=q)
            _starter_cache[key] = {"result_str": result_str, "cached_at": datetime.utcnow()}
            logger.info(f"Starter cached: '{q[:50]}'")
        except Exception as e:
            logger.warning(f"Starter cache failed for '{q[:50]}': {e}")
    logger.info("Starter cache warm-up complete (%d/%d cached)", len(_starter_cache), len(STARTER_QUERIES))


# ── Feedback schema ───────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="1 (worst) to 5 (best)")
    correction: Optional[str] = Field(None, description="Optional corrected answer")
    query: Optional[str] = Field(None, description="The original query, for gap logging")


def _load_history(db: Session, conversation_id: str, limit: int = 10) -> list:
    """Load recent messages from DB as conversation context."""
    msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.desc()).limit(limit).all()
    msgs.reverse()
    history = []
    for m in msgs:
        if m.role == "user":
            history.append({"question": m.content, "intent": "document_query", "topic": "", "answer_summary": "", "timestamp": m.created_at.isoformat()})
        elif m.role == "assistant" and history:
            history[-1]["answer_summary"] = (m.content or "")[:300]
    return history[-5:]


def _get_or_create_conversation(db: Session, user: User, request: AskRequest) -> Conversation:
    conversation = None
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == user.id,
        ).first()
    if not conversation:
        conversation = Conversation(
            user_id=user.id,
            title=request.query[:60] + ("..." if len(request.query) > 60 else ""),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _check_rate_limit(current_user.id):
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {_RATE_LIMIT_MAX} requests per minute")
    conversation = _get_or_create_conversation(db, current_user, request)

    # Load history for context
    history = _load_history(db, conversation.id)

    db.add(Message(conversation_id=conversation.id, role="user", content=request.query))
    db.commit()

    # ── Check starter cache (instant response for suggestion-box questions) ──
    cached_str = _get_cached_starter(request.query)
    if cached_str:
        result = json.loads(cached_str)
    else:
        # Normal full AI pipeline
        strategist = StrategistAgent()
        strategist.set_history(history)
        result_str = await strategist.investigate(question=request.query)
        result = json.loads(result_str)

    assistant_message = Message(
        conversation_id=conversation.id, role="assistant",
        content=result.get("answer", ""),
        agent_trace=result.get("agent_trace", []),
        citations=result.get("citations", []),
    )
    db.add(assistant_message)
    db.add(AgentRun(
        conversation_id=conversation.id, agent_type="strategist",
        input_query=request.query, output=result.get("answer", ""),
        steps=result.get("agent_trace", []),
        duration_ms=result.get("duration_ms", 0), success=True,
    ))
    # Log individual sub-agent runs from the trace so analytics reflect real usage
    seen_agents = set()
    for trace_step in result.get("agent_trace", []):
        agent_name = trace_step.get("agent", "").lower()
        if agent_name and agent_name != "strategist" and agent_name not in seen_agents:
            seen_agents.add(agent_name)
            db.add(AgentRun(
                conversation_id=conversation.id, agent_type=agent_name,
                input_query=request.query, output=trace_step.get("description", ""),
                steps=[trace_step], duration_ms=0, success=True,
            ))
    db.commit()

    followups = result.get("suggested_followups", [])

    return AskResponse(
        conversation_id=conversation.id, message_id=assistant_message.id,
        answer=result.get("answer", ""), agent_trace=result.get("agent_trace", []),
        citations=result.get("citations", []),
        suggested_followups=followups,
    )


@router.post("/ask/stream-http")
async def ask_stream_http(request: AskRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _check_rate_limit(current_user.id):
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {_RATE_LIMIT_MAX} requests per minute")
    """SSE streaming with real token-by-token output from Azure OpenAI."""
    conversation = _get_or_create_conversation(db, current_user, request)
    history = _load_history(db, conversation.id)
    conversation_id = conversation.id

    # Persist the user message BEFORE streaming starts so it exists in DB
    # regardless of whether the stream completes. The outer `db` session is
    # request-scoped and valid at this point.
    db.add(Message(conversation_id=conversation_id, role="user", content=request.query))
    db.commit()

    # ── Check starter cache for instant response ──
    cached_str = _get_cached_starter(request.query)

    if cached_str:
        # Serve cached followup as fast SSE stream (word-chunked)
        cached_result = json.loads(cached_str)

        async def cached_event_stream():
            yield f"data: {json.dumps({'type': 'start', 'message': 'Iroko AI (cached)', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            yield f"data: {json.dumps({'type': 'agent_action', 'agent': 'Strategist', 'tool': 'cache', 'description': 'Serving pre-computed starter answer', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            answer = cached_result.get("answer", "")
            words = answer.split(" ")
            for i in range(0, len(words), 4):
                chunk = " ".join(words[i:i + 4])
                if i + 4 < len(words):
                    chunk += " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            complete_event = {
                "type": "complete",
                "answer": answer,
                "citations": cached_result.get("citations", []),
                "suggested_followups": cached_result.get("suggested_followups", []),
                "agent_trace": cached_result.get("agent_trace", []),
                "duration_ms": 0,
            }
            yield f"data: {json.dumps(complete_event)}\n\n"

            # Persist to DB
            try:
                from models.database import SessionLocal
                _db = SessionLocal()
                try:
                    _db.add(Message(
                        conversation_id=conversation_id, role="assistant",
                        content=answer,
                        agent_trace=cached_result.get("agent_trace", []),
                        citations=cached_result.get("citations", []),
                    ))
                    _db.add(AgentRun(
                        conversation_id=conversation_id, agent_type="strategist",
                        input_query=request.query, output=answer,
                        steps=cached_result.get("agent_trace", []),
                        duration_ms=0, success=True,
                    ))
                    _db.commit()
                finally:
                    _db.close()
            except Exception as e:
                logger.error(f"SSE cached: DB persist failed: {e}")


            yield "data: [DONE]\n\n"

        return StreamingResponse(
            cached_event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # ── Normal full pipeline streaming ──
    strategist = StrategistAgent()
    strategist.set_history(history)

    async def event_stream():
        full_result: dict = {}
        try:
            async for event in strategist.investigate_stream(question=request.query):
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "complete":
                    full_result = event
        except Exception as e:
            logger.error(f"SSE stream generator error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted. Please retry.'})}\n\n"

        # Persist only the assistant response — user message already committed above.
        try:
            from models.database import SessionLocal
            _db = SessionLocal()
            try:
                _db.add(Message(
                    conversation_id=conversation_id, role="assistant",
                    content=full_result.get("answer", ""),
                    agent_trace=full_result.get("agent_trace", []),
                    citations=full_result.get("citations", []),
                ))
                _db.add(AgentRun(
                    conversation_id=conversation_id, agent_type="strategist",
                    input_query=request.query, output=full_result.get("answer", ""),
                    steps=full_result.get("agent_trace", []),
                    duration_ms=full_result.get("duration_ms", 0), success=bool(full_result),
                ))
                seen_agents = set()
                for trace_step in full_result.get("agent_trace", []):
                    agent_name = trace_step.get("agent", "").lower()
                    if agent_name and agent_name != "strategist" and agent_name not in seen_agents:
                        seen_agents.add(agent_name)
                        _db.add(AgentRun(
                            conversation_id=conversation_id, agent_type=agent_name,
                            input_query=request.query, output=trace_step.get("description", ""),
                            steps=[trace_step], duration_ms=0, success=True,
                        ))
                _db.commit()
            finally:
                _db.close()
        except Exception as e:
            logger.error(f"SSE: DB persist (assistant) failed: {e}")


        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.websocket("/ask/stream")
async def ask_stream(websocket: WebSocket, token: str):
    # Validate the token before accepting
    from services.auth_utils import decode_access_token
    from models.database import SessionLocal, User
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        db.close()
        if not user:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return
    await websocket.accept()
    # rest of the existing websocket handler continues unchanged
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            query = request.get("query", "")
            if not query:
                await websocket.send_json({"type": "error", "message": "No query"})
                continue

            strategist = StrategistAgent()
            async for event in strategist.investigate_stream(question=query):
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@router.get("/conversations")
async def get_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).limit(50).all()
    return {"conversations": [{"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at, "message_count": len(c.messages)} for c in conversations]}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return {"conversation_id": conversation_id, "messages": [{"id": m.id, "role": m.role, "content": m.content, "agent_trace": m.agent_trace, "citations": m.citations, "created_at": m.created_at} for m in conversation.messages]}


@router.post("/briefing")
async def morning_briefing(current_user: User = Depends(get_current_user)):
    strategist = StrategistAgent()
    result_str = await strategist.morning_briefing(user_department=current_user.department or "General")
    return json.loads(result_str)


_VOICE_UPLOAD_DIR = "/tmp/atlas_voice"
os.makedirs(_VOICE_UPLOAD_DIR, exist_ok=True)

_ALLOWED_AUDIO = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg"}
_WHISPER_DEPLOYMENT = os.getenv("AZURE_OPENAI_WHISPER_DEPLOYMENT", "whisper")


async def _transcribe_audio(file_path: str, filename: str) -> str:
    """Transcribe an audio file using Azure OpenAI Whisper. Returns transcript text."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        raise HTTPException(status_code=503, detail="Voice transcription not configured (missing Azure OpenAI credentials)")

    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    )
    with open(file_path, "rb") as f:
        response = await client.audio.transcriptions.create(
            model=_WHISPER_DEPLOYMENT,
            file=(filename, f),
        )
    return response.text


@router.post("/voice")
async def voice_ask(
    audio: UploadFile = File(..., description="Audio file (mp3, wav, m4a, webm, ogg, …)"),
    conversation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Voice chat endpoint.

    1. Accepts an audio file upload
    2. Transcribes it via Azure OpenAI Whisper
    3. Runs the transcript through the AI agent pipeline
    4. Returns the transcription + AI answer + citations
    """
    if not _check_rate_limit(current_user.id):
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {_RATE_LIMIT_MAX} requests per minute")

    filename = audio.filename or "audio.webm"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    if ext not in _ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format '{ext}'. Allowed: {', '.join(_ALLOWED_AUDIO)}")

    tmp_path = os.path.join(_VOICE_UPLOAD_DIR, f"{current_user.id}_{id(audio)}.{ext}")
    try:
        content = await audio.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        transcript = await _transcribe_audio(tmp_path, filename)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        raise HTTPException(status_code=502, detail=f"Transcription failed: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=422, detail="Could not detect speech in the audio")

    # Build or find conversation
    class _VoiceReq:
        query = transcript.strip()
        conversation_id = conversation_id

    conversation = _get_or_create_conversation(db, current_user, _VoiceReq())
    history = _load_history(db, conversation.id)

    db.add(Message(conversation_id=conversation.id, role="user", content=transcript.strip()))
    db.commit()

    strategist = StrategistAgent()
    strategist.set_history(history)
    result_str = await strategist.investigate(question=transcript.strip())
    result = json.loads(result_str)

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("answer", ""),
        agent_trace=result.get("agent_trace", []),
        citations=result.get("citations", []),
    )
    db.add(assistant_message)
    db.add(AgentRun(
        conversation_id=conversation.id,
        agent_type="strategist",
        input_query=transcript.strip(),
        output=result.get("answer", ""),
        steps=result.get("agent_trace", []),
        duration_ms=result.get("duration_ms", 0),
        success=True,
    ))
    # Log individual sub-agent runs from the trace so analytics reflect real usage
    seen_agents = set()
    for trace_step in result.get("agent_trace", []):
        agent_name = trace_step.get("agent", "").lower()
        if agent_name and agent_name != "strategist" and agent_name not in seen_agents:
            seen_agents.add(agent_name)
            db.add(AgentRun(
                conversation_id=conversation.id,
                agent_type=agent_name,
                input_query=transcript.strip(),
                output=trace_step.get("description", ""),
                steps=[trace_step],
                duration_ms=0,
                success=True,
            ))
    db.commit()

    return {
        "conversation_id": conversation.id,
        "message_id": assistant_message.id,
        "transcript": transcript.strip(),
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "suggested_followups": result.get("suggested_followups", []),
        "agent_trace": result.get("agent_trace", []),
    }


@router.post("/ask/{conversation_id}/feedback")
async def submit_feedback(
    conversation_id: str,
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record user rating on a conversation. Low ratings auto-log a knowledge gap."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.add(AuditLog(
        user_id=current_user.id,
        action="feedback",
        resource=f"conversation:{conversation_id}",
        details={
            "rating": body.rating,
            "correction": body.correction,
            "query": body.query,
        },
    ))

    # Rating ≤ 2 means the answer was poor — log as a knowledge gap so
    # document owners know what to upload
    if body.rating <= 2 and body.query:
        db.add(KnowledgeGap(
            query=body.query,
            confidence_score=0.0,
        ))

    db.commit()
    return {"status": "ok", "message": "Feedback recorded", "conversation_id": conversation_id}


# ─────────────────────────────────────────────────────────────────────────────
# Export endpoint — one-click PDF / PPTX from any AI answer
# ─────────────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    answer:     str
    citations:  list = []
    title:      str  = "Board Report"
    format:     str  = "pdf"          # "pdf" | "pptx"
    map_data:   list = []             # network heatmap regions (optional)
    fraud_data: Optional[dict] = None  # fraud intelligence summary (optional)


@router.post("/export")
async def export_report(
    req: ExportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a branded PDF or PowerPoint deck from an AI answer.
    Returns the file as an inline download — no temporary storage needed.
    """
    from services.export_service import generate_pdf, generate_pptx

    safe_title = (req.title or "Board Report")[:120]
    date_str   = datetime.utcnow().strftime("%Y%m%d")

    if req.format == "pptx":
        data      = await generate_pptx(safe_title, req.answer, req.citations, req.map_data, req.fraud_data)
        filename  = f"iroko_report_{date_str}.pptx"
        mime      = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        data      = await asyncio.to_thread(generate_pdf, safe_title, req.answer, req.citations, req.map_data, req.fraud_data)
        filename  = f"iroko_report_{date_str}.pdf"
        mime      = "application/pdf"

    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )