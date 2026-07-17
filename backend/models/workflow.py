"""
models/workflow.py — Workflow / task-management models for Iroko AI.

Turns document intelligence into ACTION: alerts, compliance verdicts, and
chat insights become routed, owned, SLA-tracked tasks. This is the
"document → insight → action" half of the MTN productivity problem statement.
"""
import enum
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON

from models.database import Base, generate_id


class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    dismissed = "dismissed"


class TaskPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TaskSource(str, enum.Enum):
    alert = "alert"                 # Watchdog alert → task
    compliance = "compliance"       # NO-GO / MONITOR verdict → task
    chat = "chat"                   # created from a chat insight
    manual = "manual"               # created by a user


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id = Column(String, primary_key=True, default=generate_id)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Provenance — what insight generated this task
    source_type = Column(String, default=TaskSource.manual)   # alert | compliance | chat | manual
    source_id = Column(String, nullable=True)                  # e.g. Alert.id / trace id
    alert_type = Column(String, nullable=True)                 # contract_expiry | policy_conflict | ...
    verdict = Column(String, nullable=True)                    # GO | MONITOR | NO-GO (compliance tasks)
    related_document_ids = Column(JSON, default=list)
    suggested_actions = Column(JSON, default=list)

    # Routing & ownership
    department = Column(String, nullable=True, index=True)     # routed department
    assigned_to_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    organisation = Column(String, nullable=True)

    # Priority / SLA
    priority = Column(String, default=TaskPriority.medium, index=True)
    status = Column(String, default=TaskStatus.open, index=True)
    sla_hours = Column(Integer, nullable=True)                 # hours allowed from creation
    due_date = Column(DateTime, nullable=True, index=True)

    # Lifecycle timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
