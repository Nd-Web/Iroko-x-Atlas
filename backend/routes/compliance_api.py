"""
Public compliance check API — POST /api/v1/compliance/check

Auth:       Authorization: Bearer <api_key>  (validated via get_user_from_api_key)
Rate limit: 60 req / 60 s per API key
            TODO: replace _rate_buckets with Redis (INCR + EXPIRE) before production
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.watchdog import WatchdogAgent
from models.database import get_db, User
from services.auth_utils import get_current_user, get_user_from_api_key
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=False)


async def _optional_jwt_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the JWT-authenticated user, or None if the token is absent/invalid."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compliance-api"])

# ---------------------------------------------------------------------------
# In-memory rate limiter — 60 requests per 60 s per API key
# TODO: replace with Redis INCR + EXPIRE before production
# ---------------------------------------------------------------------------
_rate_buckets: dict = defaultdict(lambda: (0, 0.0))
_RATE_LIMIT = 60
_RATE_WINDOW = 60.0


def _check_rate_limit(api_key: str) -> None:
    count, window_start = _rate_buckets[api_key]
    now = time.monotonic()
    if now - window_start >= _RATE_WINDOW:
        _rate_buckets[api_key] = (1, now)
        return
    if count >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 60 requests per minute")
    _rate_buckets[api_key] = (count + 1, window_start)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ComplianceCheckRequest(BaseModel):
    text: str
    context: Optional[str] = None
    sector: Optional[str] = None  # "network" (NCC) or "financial" (CBN/SEC); default financial


class ComplianceCheckResponse(BaseModel):
    verdict: str
    flags: List[str]
    reasoning: str
    regulation: str
    confidence: float
    checked_at: str


# ---------------------------------------------------------------------------
# Shared agent instance
# ---------------------------------------------------------------------------

_watchdog = WatchdogAgent()


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/compliance/check",
    response_model=ComplianceCheckResponse,
    summary="Check a statement or clause for regulatory compliance",
    responses={
        401: {"description": "Invalid or missing API key"},
        422: {"description": "Malformed request body"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Compliance engine failure"},
    },
)
async def compliance_check(
    body: ComplianceCheckRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    jwt_user: Optional[User] = Depends(_optional_jwt_user),
):
    # ── Auth: accept either a login JWT (dashboard) or an API key (external) ──
    user = jwt_user
    rate_key: str

    if user:
        # Standard dashboard login — JWT already validated by get_current_user
        rate_key = str(user.id)
    else:
        # Fallback: API key path for external/programmatic callers
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        api_key = authorization[len("Bearer "):].strip()
        user = get_user_from_api_key(api_key, db)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        rate_key = api_key

    # ── Rate limit ────────────────────────────────────────────────────────────
    _check_rate_limit(rate_key)

    # ── Compliance engine ─────────────────────────────────────────────────────
    try:
        sector = (body.sector or "network").lower()
        if sector not in ("network", "financial"):
            sector = "network"
        default_org = "MTN Nigeria" if sector == "network" else "African Fintech Platform"
        org = body.context or default_org
        raw = await _watchdog.find_policy_conflicts(organisation=org, topic=body.text, sector=sector)
        result = json.loads(raw)
        alerts = result.get("alerts", [])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Compliance engine failure for text=%r", body.text)
        return JSONResponse(
            status_code=500,
            content={"error": "Compliance check failed", "detail": str(exc)},
        )

    # ── Derive verdict ────────────────────────────────────────────────────────
    critical = [a for a in alerts if a.get("severity") == "critical"]
    warnings = [a for a in alerts if a.get("severity") == "warning"]

    if critical:
        verdict = "NO-GO"
        confidence = 0.90
    elif warnings:
        verdict = "MONITOR"
        confidence = 0.75
    else:
        verdict = "GO"
        confidence = 0.95

    flags: List[str] = [a["title"] for a in alerts if a.get("title")]

    top = (critical or warnings or alerts or [None])[0]
    reasoning = (
        top.get("summary", "No compliance issues identified.")
        if top else "No compliance issues identified."
    )
    regulation = (
        top.get("metadata", {}).get("regulation", "")
        if top else ""
    )

    return ComplianceCheckResponse(
        verdict=verdict,
        flags=flags,
        reasoning=reasoning,
        regulation=regulation,
        confidence=confidence,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
