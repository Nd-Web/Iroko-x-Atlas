"""
Voice Route — TTS (Azure Realtime), STT (Azure Whisper), and WebRTC session
minting (Azure Realtime) for the browser conversational widget.

Replaces the old Aethex proxy (frontend/app/api/agent/[...path]/route.ts),
which forwarded arbitrary paths straight to a third-party API with no
per-user auth. These endpoints sit behind the same `get_current_user` auth
as the rest of the app.

  POST /api/voice/tts         {text, voice?}          -> audio/mpeg bytes
  POST /api/voice/transcribe  multipart file          -> {transcript}
  POST /api/voice/session     {instructions?, voice?} -> {client_secret, calls_url}
  POST /api/voice/live-session {sdp, voice?}          -> {sdp, session_id, greeting}  (GPT-Live)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field

from models.database import User
from services.auth_utils import get_current_user
from services import azure_realtime
from services import azure_openai
from services import gpt_live

router = APIRouter(prefix="/api/voice", tags=["Voice"])
logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str | None = None


class SessionRequest(BaseModel):
    instructions: str = ""
    voice: str | None = None


class LiveSessionRequest(BaseModel):
    sdp: str = Field(..., min_length=1, max_length=20000)
    voice: str | None = Field(default=None, max_length=40)


@router.post("/tts")
async def tts(body: TTSRequest, current_user: User = Depends(get_current_user)):
    try:
        mp3 = azure_realtime.synthesize_speech_mp3(body.text, body.voice)
    except azure_realtime.RealtimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(content=mp3, media_type="audio/mpeg")


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    wav_bytes = await file.read()
    try:
        transcript = await azure_openai.transcribe_audio(wav_bytes, file.filename or "audio.wav")
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=400, detail=f"Transcription failed: {e}")
    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe audio")
    return {"transcript": transcript}


@router.post("/session")
async def session(body: SessionRequest, current_user: User = Depends(get_current_user)):
    try:
        return azure_realtime.mint_webrtc_client_secret(body.instructions, body.voice)
    except azure_realtime.RealtimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/live-session")
async def live_session(body: LiveSessionRequest, current_user: User = Depends(get_current_user)):
    # Instructions stay server-side: the persona and its delegation rules are not
    # a browser-controlled prompt.
    try:
        return await gpt_live.create_webrtc_session(body.sdp, voice=body.voice)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except gpt_live.LiveError as e:
        logger.warning("GPT-Live session failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
