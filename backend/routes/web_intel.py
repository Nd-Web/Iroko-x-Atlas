"""
routes/web_intel.py — Web Intelligence API routes for Iroko AI.
===============================================================
Prefix : /api/v1/intel
Tags   : Web Intelligence
Auth   : Depends(get_current_user) on all endpoints except /health
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import get_db, User
from services.auth_utils import get_current_user
from services.web_intelligence import run_all_signals
from services.brightdata import bright_data_client
from services.ncc_live_rules import ncc_rules_service  # CBN/SEC ruleset (module retained for compat)
from services.audit_service import audit_service          # ← GAP 5 FIX: singleton
from services.brief_generator import brief_generator
from services.verdict_engine import VerdictOutput
from services.fraud_intelligence import fraud_intel_service  # ← GAP 2 FIX
from agents.orchestrator import web_intel_pipeline           # ← GAP 1 FIX

router = APIRouter(prefix="/api/v1/intel", tags=["Web Intelligence"])
logger = logging.getLogger(__name__)


# ── Pydantic response models ──────────────────────────────────────────────────

class SignalsResponse(BaseModel):
    regulatory:   List[dict] = Field(default_factory=list)
    competitor:   List[dict] = Field(default_factory=list)
    vendor_risk:  List[dict] = Field(default_factory=list)
    fraud:        List[dict] = Field(default_factory=list)
    market:       List[dict] = Field(default_factory=list)
    fetched_at:   str        = Field(default="")
    category:     Optional[str] = Field(default=None)


class RegulatoryResponse(BaseModel):
    rules:        List[dict] = Field(default_factory=list)
    live_updates: List[dict] = Field(default_factory=list)
    compiled_at:  str        = Field(default="")


class ComplianceCheckRequest(BaseModel):
    decision_text: str = Field(..., min_length=1)


class AuditEntryOut(BaseModel):
    id:                  str
    agent_name:          str
    action_type:         str
    decision_summary:    str
    verdict:             Optional[str]   = None
    confidence_score:    Optional[float] = None
    ncc_regulation_ref:  Optional[str]   = None
    ncc_section_ref:     Optional[str]   = None
    source_url:          Optional[str]   = None
    workspace_id:        Optional[str]   = None
    chain_hash:          str
    created_at:          str
    model_config = {"from_attributes": True}


class AuditTrailResponse(BaseModel):
    entries:         List[AuditEntryOut]
    total:           int
    chain_integrity: Optional[dict] = Field(default=None)


# ── Helpers ───────────────────────────────────────────────────────────────────

_VALID_CATEGORIES = {"regulatory", "competitor", "vendor_risk", "fraud", "market"}


def _serialise_audit_entries(entries: list) -> List[AuditEntryOut]:
    out = []
    for e in entries:
        out.append(AuditEntryOut(
            id=str(e.id),
            agent_name=e.agent_name,
            action_type=e.action_type,
            decision_summary=e.decision_summary,
            verdict=e.verdict,
            confidence_score=e.confidence_score,
            ncc_regulation_ref=e.ncc_regulation_ref,
            ncc_section_ref=e.ncc_section_ref,
            source_url=e.source_url,
            workspace_id=e.workspace_id,
            chain_hash=e.chain_hash,
            created_at=e.created_at.isoformat() if e.created_at else "",
        ))
    return out


# ── 1. GET /signals ───────────────────────────────────────────────────────────

@router.get("/signals", response_model=SignalsResponse)
async def get_signals(
    category: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> SignalsResponse:
    if category and category not in _VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(sorted(_VALID_CATEGORIES))}",
        )
    try:
        all_signals: dict[str, Any] = await run_all_signals(bright_data_client)
    except Exception as exc:
        logger.error("[web_intel] run_all_signals failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Web intelligence fetch failed: {exc}")

    fetched_at = datetime.now(tz=timezone.utc).isoformat()

    if category:
        filtered: dict[str, Any] = {k: [] for k in _VALID_CATEGORIES}
        filtered[category] = all_signals.get(category, [])
        return SignalsResponse(**filtered, fetched_at=fetched_at, category=category)

    return SignalsResponse(
        regulatory=all_signals.get("regulatory", []),
        competitor=all_signals.get("competitor", []),
        vendor_risk=all_signals.get("vendor_risk", []),
        fraud=all_signals.get("fraud", []),
        market=all_signals.get("market", []),
        fetched_at=fetched_at,
        category=None,
    )


# ── 2. GET /regulatory ────────────────────────────────────────────────────────

@router.get("/regulatory", response_model=RegulatoryResponse)
async def get_regulatory(
    current_user: User = Depends(get_current_user),
) -> RegulatoryResponse:
    try:
        compiled: dict[str, Any] = await ncc_rules_service.compile_live_enforcement_rules()
    except Exception as exc:
        logger.error("[web_intel] compile_live_enforcement_rules failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"NCC rules compilation failed: {exc}")

    return RegulatoryResponse(
        rules=compiled.get("base_regulations", []),          # ← key fix
        live_updates=compiled.get("live_updates", []),
        compiled_at=compiled.get("compiled_at", datetime.now(tz=timezone.utc).isoformat()),
    )


# ── 3. POST /check-compliance ─────────────────────────────────────────────────

@router.post("/check-compliance", response_model=VerdictOutput)
async def check_compliance(
    body: ComplianceCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result: dict[str, Any] = await ncc_rules_service.check_decision_against_rules(
            body.decision_text
        )
    except Exception as exc:
        logger.error("[web_intel] check_decision_against_rules failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Compliance check failed: {exc}")

    verdict: str = result.get("verdict", "MONITOR")
    violations: list = result.get("violations", [])
    ncc_refs: list[str] = result.get("ncc_refs", [])

    if violations:
        summary = f"Compliance check: {len(violations)} violation(s) detected — {'; '.join(str(v) for v in violations[:3])}"
    else:
        summary = f"Compliance check passed ({verdict}) for: {body.decision_text[:120]}"

    try:
        await audit_service.log_decision(          # ← GAP 5 FIX
            db,
            agent_name="WebIntelAPI",
            action_type="compliance_check",
            decision_summary=summary,
            ncc_ref=ncc_refs[0] if ncc_refs else None,
            confidence=result.get("confidence", None),
            verdict=verdict,
        )
    except Exception as exc:
        logger.error("[web_intel] audit_service.log_decision failed: %s", exc)

    from services.verdict_engine import verdict_engine
    output = verdict_engine.format_verdict_output(
        finding={
            "summary": summary,
            "action_type": "compliance_check",
            "ncc_regulation_ref": ncc_refs[0] if ncc_refs else "",
        },
        verdict=verdict,
        sources=[],
        ncc_refs=ncc_refs,
        confidence_score=result.get("confidence", 0.0),
        compliant=result.get("compliant", True),
        violations=violations,
    )
    return output


# ── 3b. POST /compliance-pdf ──────────────────────────────────────────────────

class CompliancePdfRequest(BaseModel):
    """Full compliance verdict payload from the frontend."""
    verdict: str = Field(default="MONITOR")
    compliant: bool = Field(default=True)
    confidence_score: Optional[float] = Field(default=None)
    violations: List[dict] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    ncc_refs: List[str] = Field(default_factory=list)
    decision_text: str = Field(default="")
    summary: Optional[str] = Field(default=None)
    workspace_name: str = Field(default="African Fintech Platform")


@router.post("/compliance-pdf")
async def download_compliance_pdf(
    body: CompliancePdfRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Generate a detailed, boardroom-ready PDF directly from a compliance check result.

    Accepts the full VerdictOutput payload from the frontend and produces a
    ReportLab PDF with: verdict banner, confidence score, NCC violations table,
    decision text reviewed, recommended actions, and audit trail.
    """
    # Build the verdict_output dict that brief_generator expects
    confidence = body.confidence_score if body.confidence_score is not None else 0.0

    # Build a rich summary from the violations
    if body.violations:
        viol_lines = "; ".join(
            f"{v.get('regulation_id', 'CBN-???')} — {v.get('reason', '')}"
            for v in body.violations[:3]
        )
        summary = (
            f"NCC Compliance Check — {body.verdict}: {len(body.violations)} violation(s) detected. "
            f"{viol_lines}."
        )
    else:
        summary = (
            f"NCC Compliance Check — {body.verdict}: No violations detected for the evaluated decision."
        )

    # Build NCC violations as sources so they appear in the PDF
    violation_sources = [
        {
            "title": f"[{v.get('regulation_id', 'NCC')}] {v.get('section', '')} — {v.get('reason', '')}",
            "url": "",
        }
        for v in body.violations
    ]

    verdict_output: dict = {
        "verdict":             body.verdict,
        "compliant":           body.compliant,
        "confidence_score":    confidence,
        "summary":             summary,
        "decision_text":       body.decision_text,
        "violations":          [v for v in body.violations] if body.violations else [],
        "recommended_actions": body.recommended_actions,
        "ncc_references":      body.ncc_refs,
        "sources":             violation_sources,
        "generated_at":        datetime.now(tz=timezone.utc).isoformat(),
    }

    # Fetch recent audit trail to include in the PDF
    try:
        audit_entries_raw = await audit_service.get_audit_trail(db, limit=20)
        audit_dicts = [
            {
                "agent_name":  e.agent_name,
                "action_type": e.action_type,
                "created_at":  e.created_at.isoformat() if e.created_at else "",
                "chain_hash":  e.chain_hash,
                "verdict":     e.verdict,
            }
            for e in audit_entries_raw[:20]
        ]
    except Exception as exc:
        logger.warning("[web_intel] compliance-pdf: audit trail fetch failed: %s", exc)
        audit_dicts = []

    try:
        pdf_bytes: bytes = brief_generator.generate_brief(
            verdict_output=verdict_output,
            workspace_name=body.workspace_name,
            include_audit_trail=True,
            audit_entries=audit_dicts,
        )
    except Exception as exc:
        logger.error("[web_intel] compliance-pdf: brief_generator failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="iroko_compliance_{body.verdict.lower()}_{date_str}.pdf"',
        },
    )


# ── 4. GET /audit-trail ───────────────────────────────────────────────────────

@router.get("/audit-trail", response_model=AuditTrailResponse)
async def get_audit_trail(
    limit: int = Query(default=50, ge=1, le=500),
    action_type: Optional[str] = Query(default=None),
    verify_chain: bool = Query(default=False),
    workspace_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditTrailResponse:
    try:
        entries = await audit_service.get_audit_trail(   # ← GAP 5 FIX
            db,
            workspace_id=workspace_id,
            limit=limit,
            action_type=action_type,
        )
    except Exception as exc:
        logger.error("[web_intel] get_audit_trail failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit trail: {exc}")

    chain_integrity: Optional[dict] = None
    if verify_chain:
        try:
            chain_integrity = await audit_service.verify_chain_integrity(db, workspace_id=workspace_id)  # ← GAP 5 FIX
        except Exception as exc:
            logger.error("[web_intel] verify_chain_integrity failed: %s", exc)
            chain_integrity = {"valid": False, "error": str(exc)}

    serialised = _serialise_audit_entries(entries)
    return AuditTrailResponse(entries=serialised, total=len(serialised), chain_integrity=chain_integrity)


# ── 5. GET /brief ─────────────────────────────────────────────────────────────

@router.get("/brief")
async def get_brief(
    include_audit_trail: bool = Query(default=True),
    workspace_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        audit_entries = await audit_service.get_audit_trail(db, workspace_id=workspace_id, limit=50)  # ← GAP 5 FIX
    except Exception as exc:
        logger.error("[web_intel] get_audit_trail for brief failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to load audit data: {exc}")

    verdict_counts: dict[str, int] = {"GO": 0, "NO-GO": 0, "MONITOR": 0}
    for e in audit_entries:
        v = (e.verdict or "").upper()
        if v in verdict_counts:
            verdict_counts[v] += 1

    if verdict_counts["NO-GO"] > 0:
        aggregate_verdict = "NO-GO"
    elif verdict_counts["MONITOR"] > verdict_counts["GO"]:
        aggregate_verdict = "MONITOR"
    elif verdict_counts["GO"] > 0:
        aggregate_verdict = "GO"
    else:
        aggregate_verdict = "MONITOR"

    conf_values = [e.confidence_score for e in audit_entries if e.confidence_score is not None]
    avg_confidence = sum(conf_values) / len(conf_values) if conf_values else 0.0

    from services.verdict_engine import verdict_engine
    verdict_output: dict = verdict_engine.format_verdict_output(
        finding={
            "summary": (
                f"Compliance brief covering {len(audit_entries)} recent decisions — "
                f"{verdict_counts['GO']} GO, {verdict_counts['NO-GO']} NO-GO, "
                f"{verdict_counts['MONITOR']} MONITOR."
            ),
            "action_type": "compliance_brief",
        },
        verdict=aggregate_verdict,
        sources=[],
        ncc_refs=[],
        confidence_score=round(avg_confidence, 4),
    )

    audit_dicts: Optional[list[dict]] = None
    if include_audit_trail and audit_entries:
        audit_dicts = [
            {
                "agent_name":  e.agent_name,
                "action_type": e.action_type,
                "created_at":  e.created_at.isoformat() if e.created_at else "",
                "chain_hash":  e.chain_hash,
                "verdict":     e.verdict,
            }
            for e in audit_entries[:30]
        ]

    try:
        pdf_bytes: bytes = brief_generator.generate_brief(
            verdict_output=verdict_output,
            include_audit_trail=include_audit_trail,
            audit_entries=audit_dicts,
        )
    except Exception as exc:
        logger.error("[web_intel] brief_generator.generate_brief failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="iroko_intel_brief_{date_str}.pdf"'},
    )


# ── 6. GET /health ────────────────────────────────────────────────────────────

@router.get("/health")
async def intel_health() -> dict:
    try:
        status: dict[str, Any] = await bright_data_client.health_check()
    except Exception as exc:
        logger.warning("[web_intel] health_check failed: %s", exc)
        return {
            "status": "degraded",
            "bright_data": {"connected": False, "error": str(exc)},
            "checked_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    return {
        "status": "ok" if status.get("connected") else "degraded",
        "bright_data": status,
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── 7. GET /stream — SSE pipeline (GAP 1 FIX) ────────────────────────────────

@router.get("/stream")
async def stream_web_intel(
    query: str = Query(..., min_length=1, description="Intelligence query to run through the full pipeline"),
    workspace_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Stream the full web intelligence pipeline as Server-Sent Events.
    Each event is a JSON dict: {agent, step, content, status, timestamp}.
    Connect via EventSource at /api/v1/intel/stream?query=your+query
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for frame in web_intel_pipeline(
                query=query,
                db=db,
                workspace_id=workspace_id,
            ):
                yield f"data: {json.dumps(frame)}\n\n"
        except Exception as exc:
            logger.error("[web_intel] stream error: %s", exc)
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"
        finally:
            yield "data: {\"status\": \"closed\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── 8. GET /fraud-alert — Fraud intelligence pipeline (GAP 2 FIX) ─────────────

@router.get("/fraud-alert")
async def get_fraud_alert(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Run the full fraud intelligence pipeline:
    collect → noise filter → LLM triage → graph correlation → verdict.
    """
    try:
        result = await fraud_intel_service.generate_fraud_alert(db)
    except Exception as exc:
        logger.error("[web_intel] fraud_alert failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Fraud alert generation failed: {exc}")
    return result
