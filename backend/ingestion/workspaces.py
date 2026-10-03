"""Explicit, audited workspace provisioning. Never infer identity from profile text."""

from fastapi import HTTPException

from ingestion.access import ensure_workspace, require_document
from ingestion.db import source_lock
from ingestion.models import DocumentAccess, Membership, Revision, Workspace
from ingestion.sources import official_url
from models.database import AuditLog, User


def assign_member(db, actor, user_id, target_id):
    if actor.role != "superadmin":
        raise HTTPException(403, "Platform administrator required")
    if not db.get(User, user_id) or not db.get(Workspace, target_id):
        raise HTTPException(404, "User or workspace not found")
    current = ensure_workspace(db, user_id)
    source_lock(db, f"workspace-user:{user_id}")
    if current != target_id and db.query(DocumentAccess).filter_by(workspace_id=current).first():
        raise HTTPException(
            409, "User already has workspace documents; explicit document migration is required"
        )
    db.get(Membership, user_id).workspace_id = target_id
    db.add(
        AuditLog(
            user_id=actor.id,
            action="workspace_member_assigned",
            resource=f"users/{user_id}",
            details={"previous_workspace": current, "workspace": target_id},
        )
    )
    db.commit()


def set_shared(db, actor, document_id, shared, note):
    if actor.role != "superadmin":
        raise HTTPException(403, "Platform administrator required")
    doc = require_document(db, document_id, actor, write=True)
    revision = db.get(Revision, document_id)
    if shared:
        if not revision or not revision.is_current or doc.status != "indexed":
            raise HTTPException(409, "Only indexed current regulatory evidence can be shared")
        try:
            official_url(
                revision.provenance.get("source_url", ""), revision.provenance.get("regulator", "")
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(409, "Verified official-source provenance is required") from exc
    access = db.get(DocumentAccess, document_id)
    if access is None:
        access = DocumentAccess(
            document_id=document_id, workspace_id=ensure_workspace(db, doc.uploaded_by_id)
        )
        db.add(access)
    access.shared_regulatory = shared
    db.add(
        AuditLog(
            user_id=actor.id,
            action="document_sharing_changed",
            resource=f"documents/{document_id}",
            details={"shared_regulatory": shared, "note": note},
        )
    )
    db.commit()
