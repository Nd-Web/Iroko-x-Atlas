"""
Public compliance check API — POST /api/v1/compliance/check

Auth:       Authorization: Bearer <api_key>  (validated via get_user_from_api_key)
Rate limit: 60 req / 60 s per API key
            TODO: replace _rate_buckets with Redis (INCR + EXPIRE) before production
"""

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
from services.auth_utils import authenticate_user, get_user_from_api_key
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
        return authenticate_user(credentials=credentials, db=db)
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
    evidence: Optional[str] = None  # the deciding rule, verbatim from a retrieved document
    source: Optional[str] = None    # that document's title


# ---------------------------------------------------------------------------
# Shared agent instance
# ---------------------------------------------------------------------------

_watchdog = WatchdogAgent()


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

UNVERIFIED_FLAG = "Not covered by Iroko's regulation library"


def derive_verdict(assessment: dict) -> dict:
    """
    Map the engine's assessment to GO / MONITOR / NO-GO.

    Every GO, NO-GO or MONITOR stands on a deciding rule quoted verbatim from a
    retrieved document ("evidence"). Without one, the answer is an unverified
    MONITOR — never GO, because the absence of a finding is not evidence of
    compliance.
    """
    kind = assessment.get("assessment", "")
    basis = assessment.get("basis", "")
    evidence = assessment.get("evidence") or {}
    alerts = assessment.get("alerts", []) if evidence else []
    if evidence and not alerts and kind in ("breach", "needs_safeguards"):
        alerts = [{"severity": "critical" if kind == "breach" else "warning",
                   "title": (basis or evidence["quote"])[:120], "summary": basis or evidence["quote"],
                   "metadata": {"regulation": basis}}]
    cited = {"evidence": evidence.get("quote"), "source": evidence.get("title") or None}

    # The assessment decides; alert severity only matters when the assessment is unclear.
    # (Models embellish labels — "critical for a breach" — or tag a safeguard "critical".)
    def severity(alert):
        if kind in ("breach", "needs_safeguards"):
            return "critical" if kind == "breach" else "warning"
        label = str(alert.get("severity", "")).lower()
        return "critical" if "critical" in label else "warning"

    critical = [a for a in alerts if severity(a) == "critical"]
    warnings = [a for a in alerts if severity(a) == "warning"]
    top = (critical or warnings or [None])[0]
    if top:
        return {
            "verdict": "NO-GO" if critical else "MONITOR",
            "confidence": 0.90 if critical else 0.75,
            "flags": [a["title"] for a in alerts if a.get("title")],
            "reasoning": top.get("summary") or basis,
            "regulation": (top.get("metadata") or {}).get("regulation") or basis or evidence.get("title", ""),
            **cited,
        }
    if evidence and kind == "compliant":
        return {"verdict": "GO", "confidence": 0.85, "flags": [], "reasoning": basis or evidence["quote"],
                "regulation": basis or evidence.get("title", ""), **cited}

    missing = assessment.get("missing_source", "")
    reasoning = ("Iroko could not verify this: its regulation library has no rule that decides it, "
                 "so it cannot be cleared. Confirm it against the governing regulation before proceeding.")
    if missing:
        reasoning += f" It is most likely governed by {missing}, which is not in the library."
    return {"verdict": "MONITOR", "confidence": 0.30, "flags": [UNVERIFIED_FLAG],
            "reasoning": reasoning, "regulation": "", "evidence": None, "source": None}


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
        sector = (body.sector or "financial").lower()
        if sector not in ("network", "financial"):
            sector = "financial"
        default_org = "MTN Nigeria" if sector == "network" else "African Fintech Platform"
        org = body.context or default_org
        from ingestion.access import as_user
        with as_user(user):
            assessment = await _watchdog.assess_proposed_action(topic=body.text, sector=sector)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Compliance engine failure for text=%r", body.text)
        return JSONResponse(
            status_code=500,
            content={"error": "Compliance check failed", "detail": str(exc)},
        )

    # ── Derive verdict ────────────────────────────────────────────────────────
    result = derive_verdict(assessment)
    # ── Compliance graph: is the deciding rule still the current rule? (flags only) ──
    try:
        from ingestion.access import as_user as _as_user
        from services.compliance_graph.verdicts import apply_rule_status
        with _as_user(user):
            result = apply_rule_status(db, user, assessment, result)
    except Exception:
        logger.exception("Compliance graph rule check skipped")
    verdict = result["verdict"]
    confidence = result["confidence"]
    flags: List[str] = result["flags"]
    reasoning = result["reasoning"]
    regulation = result["regulation"]

    # ── Workflow hook: NO-GO / MONITOR verdicts become actionable tasks ──────
    try:
        from services.workflow_service import create_task_from_verdict
        with as_user(user):
            task = create_task_from_verdict(
                db,
                verdict=verdict,
                subject_text=body.text,
                reasoning=reasoning,
                regulation=regulation,
                organisation=getattr(user, "organisation", None) or org,
            )
            if task:
                db.commit()
                logger.info("Compliance verdict %s → workflow task '%s'", verdict, task.title)
    except Exception:
        logger.exception("Failed to create workflow task from compliance verdict")
        db.rollback()

    return ComplianceCheckResponse(
        verdict=verdict,
        flags=flags,
        reasoning=reasoning,
        regulation=regulation,
        confidence=confidence,
        checked_at=datetime.now(timezone.utc).isoformat(),
        evidence=result["evidence"],
        source=result["source"],
    )
