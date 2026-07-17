"""
Workflows Route — document → insight → action task management.

Tasks are auto-generated from Watchdog alerts and compliance verdicts
(see services/workflow_service.py) and managed here: list, create,
assign, transition, and real workflow statistics.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import get_db, User, Alert, AuditLog
from models.workflow import WorkflowTask, TaskStatus, TaskPriority, TaskSource
from services.auth_utils import get_current_user
from services.workflow_service import (
    create_task_from_alert,
    route_department,
    workflow_stats,
)

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])
logger = logging.getLogger(__name__)

_VALID_STATUSES = {s.value for s in TaskStatus}
_VALID_PRIORITIES = {p.value for p in TaskPriority}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    description: Optional[str] = None
    department: Optional[str] = None
    priority: str = TaskPriority.medium.value
    sla_hours: Optional[int] = Field(default=None, ge=1, le=24 * 90)
    related_document_ids: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    department: Optional[str] = None
    assigned_to_id: Optional[str] = None
    description: Optional[str] = None


def _task_out(t: WorkflowTask, users_by_id: Optional[dict] = None) -> dict:
    now = datetime.utcnow()
    overdue = bool(
        t.due_date
        and t.status in (TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked)
        and t.due_date < now
    )
    assignee = None
    if t.assigned_to_id and users_by_id:
        u = users_by_id.get(t.assigned_to_id)
        if u:
            assignee = {"id": u.id, "name": u.full_name or u.email}
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "source_type": t.source_type,
        "source_id": t.source_id,
        "alert_type": t.alert_type,
        "verdict": t.verdict,
        "department": t.department,
        "priority": t.priority,
        "status": t.status,
        "sla_hours": t.sla_hours,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "overdue": overdue,
        "assigned_to": assignee,
        "suggested_actions": t.suggested_actions or [],
        "related_document_ids": t.related_document_ids or [],
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    department: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List workflow tasks with optional filters. status='active' = open+in_progress+blocked."""
    q = db.query(WorkflowTask)
    if status == "active":
        q = q.filter(WorkflowTask.status.in_(
            [TaskStatus.open, TaskStatus.in_progress, TaskStatus.blocked]))
    elif status and status != "all":
        q = q.filter(WorkflowTask.status == status)
    if department:
        q = q.filter(WorkflowTask.department == department)
    if priority:
        q = q.filter(WorkflowTask.priority == priority)

    tasks = q.order_by(WorkflowTask.created_at.desc()).limit(min(limit, 500)).all()
    user_ids = {t.assigned_to_id for t in tasks if t.assigned_to_id}
    users_by_id = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids else {}
    )
    return {"tasks": [_task_out(t, users_by_id) for t in tasks], "total": len(tasks)}


@router.get("/stats")
async def get_workflow_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real aggregates over workflow tasks (status/priority/department, overdue, cycle time)."""
    return workflow_stats(db)


@router.post("/tasks")
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually create a task."""
    if body.priority not in _VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {sorted(_VALID_PRIORITIES)}")
    sla = body.sla_hours or 72
    task = WorkflowTask(
        title=body.title.strip(),
        description=body.description,
        source_type=TaskSource.manual,
        department=body.department or current_user.department or "Operations",
        organisation=current_user.organisation,
        priority=body.priority,
        status=TaskStatus.open,
        sla_hours=sla,
        due_date=datetime.utcnow() + timedelta(hours=sla),
        related_document_ids=body.related_document_ids,
        created_by_id=current_user.id,
    )
    db.add(task)
    db.add(AuditLog(
        user_id=current_user.id, action="task_created",
        resource="workflows/tasks", details={"title": task.title},
    ))
    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update status / priority / assignment. Status transitions stamp lifecycle timestamps."""
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.status is not None:
        if body.status not in _VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_VALID_STATUSES)}")
        task.status = body.status
        now = datetime.utcnow()
        if body.status == TaskStatus.in_progress and not task.started_at:
            task.started_at = now
        if body.status in (TaskStatus.done, TaskStatus.dismissed):
            task.completed_at = now
        else:
            task.completed_at = None
    if body.priority is not None:
        if body.priority not in _VALID_PRIORITIES:
            raise HTTPException(status_code=422, detail=f"priority must be one of {sorted(_VALID_PRIORITIES)}")
        task.priority = body.priority
    if body.department is not None:
        task.department = body.department
    if body.description is not None:
        task.description = body.description
    if body.assigned_to_id is not None:
        if body.assigned_to_id == "":
            task.assigned_to_id = None
        else:
            assignee = db.query(User).filter(User.id == body.assigned_to_id).first()
            if not assignee:
                raise HTTPException(status_code=404, detail="Assignee not found")
            task.assigned_to_id = assignee.id

    db.add(AuditLog(
        user_id=current_user.id, action="task_updated",
        resource=f"workflows/tasks/{task_id}",
        details={"title": task.title, "status": task.status},
    ))
    db.commit()
    db.refresh(task)
    users_by_id = {}
    if task.assigned_to_id:
        u = db.query(User).filter(User.id == task.assigned_to_id).first()
        if u:
            users_by_id[u.id] = u
    return _task_out(task, users_by_id)


@router.post("/generate")
async def generate_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full document→insight→action sweep: run the Watchdog over the indexed
    corpus, persist any new alerts, and convert them into routed, SLA-tracked
    tasks. Returns what was created.
    """
    from agents.watchdog import WatchdogAgent

    organisation = current_user.organisation or "MTN Nigeria"
    watchdog = WatchdogAgent()
    result = json.loads(await watchdog.run_all_checks(organisation=organisation))

    alerts_created, tasks_created = 0, 0
    for alert_data in result.get("alerts", []):
        title = alert_data.get("title", "")
        alert = db.query(Alert).filter(
            Alert.title == title,
            Alert.organisation == organisation,
            Alert.status.in_(["new", "acknowledged"]),
        ).first()
        if not alert:
            alert = Alert(
                title=title,
                summary=alert_data.get("summary", ""),
                severity=alert_data.get("severity", "info"),
                alert_type=alert_data.get("alert_type", "general"),
                extra_metadata=alert_data.get("metadata", {}),
                suggested_actions=alert_data.get("suggested_actions", []),
                organisation=organisation,
            )
            db.add(alert)
            db.flush()  # get alert.id
            alerts_created += 1
        task = create_task_from_alert(db, alert.id, alert_data, organisation)
        if task:
            tasks_created += 1

    db.add(AuditLog(
        user_id=current_user.id, action="tasks_generated",
        resource="workflows/generate",
        details={"alerts_created": alerts_created, "tasks_created": tasks_created},
    ))
    db.commit()

    return {
        "alerts_found": result.get("total_alerts", 0),
        "alerts_created": alerts_created,
        "tasks_created": tasks_created,
    }
