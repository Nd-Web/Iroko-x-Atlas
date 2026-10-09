"""
services/workflow_service.py — document → insight → action.

Routes Watchdog alerts and compliance verdicts into owned, SLA-tracked
WorkflowTask rows, and computes real workflow/productivity statistics.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.workflow import WorkflowTask, TaskStatus, TaskPriority, TaskSource

logger = logging.getLogger(__name__)

# ── Routing rules ─────────────────────────────────────────────────────────────
# alert_type → owning department. Mirrors how MTN teams actually split this work.
_DEPARTMENT_ROUTING: dict[str, str] = {
    "contract_expiry": "Procurement",
    "contract_renewal": "Procurement",
    "sla_breach": "Network Operations",
    "complaint_spike": "Customer Experience",
    "policy_conflict": "Regulatory Affairs",
    "regulatory_deadline": "Regulatory Affairs",
    "compliance_verdict": "Regulatory Affairs",
    "fraud_signal": "Revenue Assurance",
    "network_incident": "Network Operations",
    "graph_review": "Compliance",
    "change_impact": "Compliance",
}
_DEFAULT_DEPARTMENT = "Operations"

# severity → (priority, SLA hours). Critical items get a 24h clock.
_SLA_BY_SEVERITY: dict[str, tuple[str, int]] = {
    "critical": (TaskPriority.critical, 24),
    "warning": (TaskPriority.high, 72),
    "info": (TaskPriority.medium, 24 * 7),
}

_VERDICT_SLA: dict[str, tuple[str, int]] = {
    "NO-GO": (TaskPriority.critical, 24),
    "MONITOR": (TaskPriority.high, 72),
}


def route_department(alert_type: Optional[str]) -> str:
    return _DEPARTMENT_ROUTING.get((alert_type or "").lower(), _DEFAULT_DEPARTMENT)


def create_task_from_alert(
    db: Session,
    alert_id: Optional[str],
    alert_data: dict[str, Any],
    organisation: Optional[str] = None,
) -> Optional[WorkflowTask]:
    """
    Convert one Watchdog alert dict into a routed, SLA-tracked task.
    Dedupes on (title, open-ish status) so re-running the Watchdog is safe.
    Returns the created task, or None when deduped.
    """
    title = (alert_data.get("title") or "").strip()
    if not title:
        return None

    existing = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.title == title,
            WorkflowTask.status.in_([TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked]),
        )
        .first()
    )
    if existing:
        return None

    severity = (alert_data.get("severity") or "info").lower()
    priority, sla_hours = _SLA_BY_SEVERITY.get(severity, _SLA_BY_SEVERITY["info"])
    alert_type = alert_data.get("alert_type") or "general"
    verdict = None
    v = alert_data.get("verdict")
    if isinstance(v, dict):
        verdict = v.get("verdict")
    elif isinstance(v, str):
        verdict = v

    task = WorkflowTask(
        title=title,
        description=alert_data.get("summary", ""),
        source_type=TaskSource.alert,
        source_id=alert_id,
        alert_type=alert_type,
        verdict=verdict,
        related_document_ids=alert_data.get("related_document_ids", []) or [],
        suggested_actions=alert_data.get("suggested_actions", []) or [],
        department=route_department(alert_type),
        organisation=organisation,
        priority=priority,
        status=TaskStatus.open,
        sla_hours=sla_hours,
        due_date=datetime.utcnow() + timedelta(hours=sla_hours),
    )
    db.add(task)
    return task


def create_task_from_verdict(
    db: Session,
    verdict: str,
    subject_text: str,
    reasoning: str = "",
    regulation: Optional[str] = None,
    source_id: Optional[str] = None,
    organisation: Optional[str] = None,
) -> Optional[WorkflowTask]:
    """
    A NO-GO / MONITOR compliance verdict becomes an actionable follow-up task
    for Regulatory Affairs. GO verdicts create nothing.
    """
    verdict = (verdict or "").upper()
    if verdict not in _VERDICT_SLA:
        return None

    priority, sla_hours = _VERDICT_SLA[verdict]
    title = f"[{verdict}] Compliance review: {subject_text[:110]}"

    existing = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.title == title,
            WorkflowTask.status.in_([TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked]),
        )
        .first()
    )
    if existing:
        return None

    description = reasoning or subject_text
    if regulation:
        description += f"\n\nRegulation: {regulation}"

    task = WorkflowTask(
        title=title,
        description=description,
        source_type=TaskSource.compliance,
        source_id=source_id,
        alert_type="compliance_verdict",
        verdict=verdict,
        department=route_department("compliance_verdict"),
        organisation=organisation,
        priority=priority,
        status=TaskStatus.open,
        sla_hours=sla_hours,
        due_date=datetime.utcnow() + timedelta(hours=sla_hours),
    )
    db.add(task)
    return task


_OPEN = [TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked]


def upsert_graph_task(
    db: Session,
    *,
    workspace_id: str,
    source_type: str,
    source_id: str,
    title: str,
    description: str = "",
    priority: str = TaskPriority.medium,
    sla_hours: int = 72,
    related_document_ids: Optional[list] = None,
    assigned_to_id: Optional[str] = None,
) -> WorkflowTask:
    """One open task per (source_type, source_id): created once, then kept current.

    Called from the compliance-graph worker, which has no signed-in user, so the
    task's workspace is recorded explicitly (record_access would otherwise leave
    it invisible to everyone).
    """
    existing = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.source_type == source_type, WorkflowTask.source_id == source_id,
                WorkflowTask.status.in_(_OPEN))
        .first()
    )
    if existing:
        existing.title = title[:300]
        existing.description = description
        existing.related_document_ids = list(related_document_ids or existing.related_document_ids or [])
        return existing
    task = WorkflowTask(
        title=title[:300],
        description=description,
        source_type=source_type,
        source_id=source_id,
        alert_type=source_type,
        related_document_ids=list(related_document_ids or []),
        department=route_department(source_type),
        assigned_to_id=assigned_to_id,
        priority=priority,
        status=TaskStatus.open,
        sla_hours=sla_hours,
        due_date=datetime.utcnow() + timedelta(hours=sla_hours),
    )
    db.add(task)
    db.flush()
    from ingestion.access import principal
    from ingestion.models import RecordAccess

    if principal.get() is None and db.get(RecordAccess, ("task", task.id)) is None:
        db.add(RecordAccess(kind="task", record_id=task.id, workspace_id=workspace_id))
    return task


def close_graph_task(db: Session, source_type: str, source_id: str) -> None:
    for task in (db.query(WorkflowTask)
                 .filter(WorkflowTask.source_type == source_type, WorkflowTask.source_id == source_id,
                         WorkflowTask.status.in_(_OPEN))):
        task.status = TaskStatus.done
        task.completed_at = datetime.utcnow()


def workflow_stats(db: Session) -> dict[str, Any]:
    """Real aggregates over workflow_tasks — no synthesized numbers."""
    now = datetime.utcnow()

    by_status = dict(
        db.query(WorkflowTask.status, func.count(WorkflowTask.id))
        .group_by(WorkflowTask.status)
        .all()
    )
    by_priority = dict(
        db.query(WorkflowTask.priority, func.count(WorkflowTask.id))
        .filter(WorkflowTask.status.in_([TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked]))
        .group_by(WorkflowTask.priority)
        .all()
    )
    by_department = [
        {"department": dept or "Unassigned", "open_tasks": count}
        for dept, count in (
            db.query(WorkflowTask.department, func.count(WorkflowTask.id))
            .filter(WorkflowTask.status.in_([TaskStatus.open, TaskStatus.in_progress]))
            .group_by(WorkflowTask.department)
            .order_by(func.count(WorkflowTask.id).desc())
            .all()
        )
    ]

    overdue = (
        db.query(func.count(WorkflowTask.id))
        .filter(
            WorkflowTask.status.in_([TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked]),
            WorkflowTask.due_date.isnot(None),
            WorkflowTask.due_date < now,
        )
        .scalar()
        or 0
    )

    # Average completion time over done tasks (hours)
    done_tasks = (
        db.query(WorkflowTask.created_at, WorkflowTask.completed_at)
        .filter(WorkflowTask.status == TaskStatus.done, WorkflowTask.completed_at.isnot(None))
        .all()
    )
    if done_tasks:
        total_h = sum((c2 - c1).total_seconds() / 3600 for c1, c2 in done_tasks)
        avg_completion_hours = round(total_h / len(done_tasks), 1)
    else:
        avg_completion_hours = None

    completed_this_week = (
        db.query(func.count(WorkflowTask.id))
        .filter(
            WorkflowTask.status == TaskStatus.done,
            WorkflowTask.completed_at >= now - timedelta(days=7),
        )
        .scalar()
        or 0
    )

    return {
        "total": db.query(func.count(WorkflowTask.id)).scalar() or 0,
        "by_status": by_status,
        "open_by_priority": by_priority,
        "open_by_department": by_department,
        "overdue": overdue,
        "completed_this_week": completed_this_week,
        "avg_completion_hours": avg_completion_hours,
    }
