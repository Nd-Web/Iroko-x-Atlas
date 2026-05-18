"""
routes/insights.py — Full CRUD REST API for AI-generated insights.

All routes require a valid JWT (Bearer token).

Endpoints
---------
GET    /insights                  List insights (paginated + filterable)
GET    /insights/{id}             Get a single insight by ID
PATCH  /insights/{id}/review      Mark an insight as reviewed
PATCH  /insights/{id}/dismiss     Mark an insight as dismissed
DELETE /insights/{id}             Hard-delete an insight
"""

from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from services.auth_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["insights"])


# ── Response / Request schemas ────────────────────────────────────────────────


class InsightOut(BaseModel):
    id: str
    org_id: Optional[str]
    document_id: Optional[str]
    title: str
    summary: str
    category: str
    severity: int
    agent_source: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


class InsightListResponse(BaseModel):
    insights: list[InsightOut]
    total: int
    page: int
    page_size: int


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fmt_dt(dt) -> str:
    if dt is None:
        return datetime.utcnow().isoformat() + "Z"
    if hasattr(dt, "isoformat"):
        return dt.isoformat() + ("Z" if dt.tzinfo is None else "")
    return str(dt)


def _row_to_out(row) -> InsightOut:
    return InsightOut(
        id=str(row.id),
        org_id=str(row.org_id) if row.org_id else None,
        document_id=str(row.document_id) if row.document_id else None,
        title=row.title,
        summary=row.summary,
        category=row.category,
        severity=int(row.severity),
        agent_source=row.agent_source,
        status=str(row.status.value if hasattr(row.status, "value") else row.status),
        created_at=_fmt_dt(row.created_at),
    )


def _get_insight_or_404(id: str, db: Session):
    """Fetch an Alert or mock-insight from DB, raise 404 if missing."""
    try:
        from models.database import Alert
        row = db.query(Alert).filter(Alert.id == id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Insight not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"_get_insight_or_404: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("", response_model=InsightListResponse)
async def list_insights(
    org_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity_min: Optional[int] = Query(None, ge=1, le=10),
    severity_max: Optional[int] = Query(None, ge=1, le=10),
    insight_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return a paginated list of insights, optionally filtered by org, category,
    severity range, and status.
    """
    try:
        from models.database import Alert

        q = db.query(Alert)

        if org_id:
            q = q.filter(Alert.organisation == org_id)
        if category:
            q = q.filter(Alert.alert_type == category)
        if insight_status:
            q = q.filter(Alert.status == insight_status)

        total = q.count()
        rows = (
            q.order_by(Alert.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        insights_out = []
        for row in rows:
            try:
                # Adapt Alert model fields to InsightOut schema
                insights_out.append(
                    InsightOut(
                        id=str(row.id),
                        org_id=row.organisation,
                        document_id=(
                            str(row.related_document_ids[0])
                            if row.related_document_ids
                            else None
                        ),
                        title=row.title,
                        summary=row.summary,
                        category=str(row.alert_type),
                        severity=_severity_from_alert(row),
                        agent_source="WatchdogAgent",
                        status=str(row.status.value if hasattr(row.status, "value") else row.status),
                        created_at=_fmt_dt(row.created_at),
                    )
                )
            except Exception:
                continue

        return InsightListResponse(
            insights=insights_out,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as exc:
        logger.error(f"list_insights error: {exc}", exc_info=True)
        # Return empty list rather than crashing
        return InsightListResponse(insights=[], total=0, page=page, page_size=page_size)


def _severity_from_alert(row) -> int:
    """Map an Alert severity string to a 1-10 int."""
    sev = str(getattr(row, "severity", "info")).lower()
    mapping = {"critical": 9, "warning": 5, "info": 2}
    return mapping.get(sev, 5)


@router.get("/{insight_id}", response_model=InsightOut)
async def get_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch a single insight by ID."""
    row = _get_insight_or_404(insight_id, db)
    return InsightOut(
        id=str(row.id),
        org_id=getattr(row, "organisation", None),
        document_id=(
            str(row.related_document_ids[0]) if row.related_document_ids else None
        ),
        title=row.title,
        summary=row.summary,
        category=str(row.alert_type),
        severity=_severity_from_alert(row),
        agent_source="WatchdogAgent",
        status=str(row.status.value if hasattr(row.status, "value") else row.status),
        created_at=_fmt_dt(row.created_at),
    )


@router.patch("/{insight_id}/review", response_model=InsightOut)
async def review_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark an insight as reviewed."""
    row = _get_insight_or_404(insight_id, db)
    row.status = "acknowledged"
    db.commit()
    db.refresh(row)
    return InsightOut(
        id=str(row.id),
        org_id=getattr(row, "organisation", None),
        document_id=None,
        title=row.title,
        summary=row.summary,
        category=str(row.alert_type),
        severity=_severity_from_alert(row),
        agent_source="WatchdogAgent",
        status="reviewed",
        created_at=_fmt_dt(row.created_at),
    )


@router.patch("/{insight_id}/dismiss", response_model=InsightOut)
async def dismiss_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dismiss an insight."""
    row = _get_insight_or_404(insight_id, db)
    row.status = "dismissed"
    db.commit()
    db.refresh(row)
    return InsightOut(
        id=str(row.id),
        org_id=getattr(row, "organisation", None),
        document_id=None,
        title=row.title,
        summary=row.summary,
        category=str(row.alert_type),
        severity=_severity_from_alert(row),
        agent_source="WatchdogAgent",
        status="dismissed",
        created_at=_fmt_dt(row.created_at),
    )


@router.delete("/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Permanently delete an insight."""
    row = _get_insight_or_404(insight_id, db)
    db.delete(row)
    db.commit()
