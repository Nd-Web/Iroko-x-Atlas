"""
Alerts Route — Watchdog alert management endpoints.
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from models.database import get_db, User, Alert, AuditLog
from models.schemas import AlertListResponse, AlertResponse
from services.auth_utils import get_current_user
from agents.watchdog import WatchdogAgent

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])
logger = logging.getLogger(__name__)


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    status: str = "new",
    severity: str = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all alerts, optionally filtered by status and severity."""
    query = db.query(Alert)

    if status and status != "all":
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    total = query.count()
    critical = sum(1 for a in alerts if a.severity == "critical")
    warnings = sum(1 for a in alerts if a.severity == "warning")

    return AlertListResponse(
        alerts=alerts,
        total=total,
        critical_count=critical,
        warning_count=warnings,
    )


@router.post("/refresh")
async def refresh_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger the Watchdog to run all checks and create new alerts.
    Called by the scheduler every hour, or manually from the dashboard.
    """
    watchdog = WatchdogAgent()
    result_str = await watchdog.run_all_checks(
        organisation=current_user.organisation or "MTN Nigeria"
    )
    result = json.loads(result_str)

    # Save new alerts to database, deduplicating by title + org
    organisation = current_user.organisation or "MTN Nigeria"
    created = 0
    for alert_data in result.get("alerts", []):
        title = alert_data.get("title", "")
        existing = db.query(Alert).filter(
            Alert.title == title,
            Alert.organisation == organisation,
            Alert.status.in_(["new", "acknowledged"]),
        ).first()
        if existing:
            continue
        db.add(Alert(
            title=title,
            summary=alert_data.get("summary", ""),
            severity=alert_data.get("severity", "info"),
            alert_type=alert_data.get("alert_type", "general"),
            extra_metadata=alert_data.get("metadata", {}),
            suggested_actions=alert_data.get("suggested_actions", []),
            organisation=organisation,
        ))
        created += 1

    db.commit()

    return {
        "created": created,
        "total_found": result.get("total_alerts", 0),
        "critical": result.get("critical_count", 0),
        "warnings": result.get("warning_count", 0),
    }


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an alert as acknowledged."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.utcnow()
    db.add(AuditLog(
        user_id=current_user.id,
        action="alert_acknowledged",
        resource=f"alerts/{alert_id}",
        details={"title": alert.title, "severity": alert.severity},
    ))
    db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.patch("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an alert as resolved."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    db.add(AuditLog(
        user_id=current_user.id,
        action="alert_resolved",
        resource=f"alerts/{alert_id}",
        details={"title": alert.title, "severity": alert.severity},
    ))
    db.commit()

    return {"message": "Alert resolved", "alert_id": alert_id}


@router.post("/{alert_id}/draft-response")
async def draft_alert_response(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ask Scribe to draft a response for this alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    from agents.scribe import ScribeAgent
    scribe = ScribeAgent()

    draft_str = await scribe.draft_email(
        purpose=f"Respond to: {alert.title}",
        context=alert.summary,
        recipient_type="internal",
        tone="professional",
    )
    draft = json.loads(draft_str)

    # Save draft to alert
    alert.draft_content = draft.get("content", "")
    db.commit()

    return {
        "alert_id": alert_id,
        "draft": draft,
    }
