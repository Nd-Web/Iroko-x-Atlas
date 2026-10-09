"""
When to re-run graph work. Each function only queues jobs (row inserts) inside
the caller's transaction; the caller commits. Nothing runs when the graph is
disabled.
"""

from __future__ import annotations

from ingestion.models import DocumentAccess
from ingestion.queue import enqueue

from services.compliance_graph.common import enabled


def active_workspaces(db) -> set[str]:
    """Workspaces that use the graph: a licence profile, controls, decisions or a sync record."""
    from models.compliance_graph import Control, InstitutionProfile, ObligationStatus, WorkspaceSync

    found: set[str] = set()
    for model, column in ((InstitutionProfile, InstitutionProfile.workspace_id),
                          (Control, Control.workspace_id),
                          (ObligationStatus, ObligationStatus.workspace_id),
                          (WorkspaceSync, WorkspaceSync.workspace_id)):
        found.update(row[0] for row in db.query(column).distinct() if row[0])
    return found


def workspaces_seeing(db, document_id: str) -> set[str]:
    access = db.get(DocumentAccess, document_id)
    if access is None:
        return set()
    if access.shared_regulatory:
        return active_workspaces(db) | {access.workspace_id}
    return {access.workspace_id}


def enqueue_workspace(db, workspace_id: str | None) -> None:
    """Queue a sync; if one is already running, ask it to run again when it finishes."""
    if not (enabled() and workspace_id):
        return
    from ingestion.models import Job
    from models.compliance_graph import WorkspaceSync

    job = db.get(Job, f"graph_ws:{workspace_id}")
    if job is not None and job.state == "running":
        sync = db.get(WorkspaceSync, workspace_id)
        if sync is None:
            sync = WorkspaceSync(workspace_id=workspace_id)
            db.add(sync)
        sync.rerun_requested = True
    enqueue(db, "graph_ws", workspace_id)


def enqueue_document(db, document_id: str) -> None:
    """Queue extraction; if it is already running, ask it to run again when it finishes."""
    if not (enabled() and document_id):
        return
    from ingestion.models import Job
    from models.compliance_graph import GraphDocument

    job = db.get(Job, f"graph:{document_id}")
    if job is not None and job.state == "running":
        gd = db.get(GraphDocument, document_id)
        if gd is not None:
            gd.rerun_requested = True
    enqueue(db, "graph", document_id)


def after_document_change(db, document_id: str) -> None:
    """Archive, rejection or a finished extraction: every workspace that can see it re-syncs."""
    for workspace_id in workspaces_seeing(db, document_id):
        enqueue_workspace(db, workspace_id)


def after_sharing_change(db, document_id: str) -> None:
    """Shared or unshared: every graph workspace may have gained or lost the document."""
    for workspace_id in active_workspaces(db):
        enqueue_workspace(db, workspace_id)
    access = db.get(DocumentAccess, document_id)
    if access is not None:
        enqueue_workspace(db, access.workspace_id)


def after_library_review(db, document_ids) -> None:
    seen: set[str] = set()
    for document_id in document_ids or ():
        seen |= workspaces_seeing(db, document_id)
    for workspace_id in seen:
        enqueue_workspace(db, workspace_id)
