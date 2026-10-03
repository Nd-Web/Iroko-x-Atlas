"""Scope document-derived records consistently across legacy dashboard routes."""

from sqlalchemy import event, exists, func, select
from sqlalchemy.orm import Session, with_loader_criteria

from ingestion.access import principal
from ingestion.models import DocumentAccess, Membership, RecordAccess
from models.database import AgentRun, Alert, AuditLog, KnowledgeGap, OrgMemory, generate_id
from models.workflow import WorkflowTask

KINDS = {
    Alert: "alert",
    AuditLog: "audit",
    KnowledgeGap: "gap",
    AgentRun: "run",
    WorkflowTask: "task",
    OrgMemory: "memory",
}


def predicate(model, actor):
    membership = (
        select(Membership.workspace_id).where(Membership.user_id == actor.id).scalar_subquery()
    )
    workspace = func.coalesce(membership, f"user:{actor.id}")
    return exists(
        select(RecordAccess.record_id).where(
            RecordAccess.kind == KINDS[model],
            RecordAccess.record_id == model.id,
            RecordAccess.workspace_id == workspace,
        )
    )


def scope_reads(state):
    actor = principal.get()
    if actor is None or not (state.is_select or state.is_update or state.is_delete):
        return
    from ingestion.db import prepare_session

    prepare_session(state.session)
    for model in KINDS:
        state.statement = state.statement.options(
            with_loader_criteria(
                model,
                predicate(model, actor),
                include_aliases=True,
            )
        )


def scope_new_records(db, flush_context, instances):
    from ingestion.access import workspace_id

    actor = principal.get()
    for row in list(db.new):
        kind = KINDS.get(type(row))
        if not kind:
            continue
        workspace = None
        if actor is not None:
            workspace = workspace_id(db, actor.id)
        elif isinstance(row, AuditLog) and row.user_id:
            workspace = workspace_id(db, row.user_id)
        elif isinstance(row, AuditLog) and (row.resource or "").startswith("documents/"):
            access = db.get(DocumentAccess, row.resource.split("/", 1)[1])
            workspace = access.workspace_id if access else None
        elif (
            isinstance(row, Alert)
            and row.alert_type == "regulatory_document"
            and len(row.related_document_ids or []) == 1
        ):
            access = db.get(DocumentAccess, row.related_document_ids[0])
            workspace = access.workspace_id if access else None
        if workspace is None:
            continue  # Unattributable legacy/background data remains quarantined.
        if row.id is None:
            row.id = generate_id()
        db.add(RecordAccess(kind=kind, record_id=row.id, workspace_id=workspace))


def install_access_handlers():
    """Idempotent registration for API, CLI worker and scoped service calls."""
    if not event.contains(Session, "do_orm_execute", scope_reads):
        event.listen(Session, "do_orm_execute", scope_reads)
    if not event.contains(Session, "before_flush", scope_new_records):
        event.listen(Session, "before_flush", scope_new_records)
