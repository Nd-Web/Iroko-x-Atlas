"""
Who may change what. Plain exceptions; routes/compliance_graph.py maps them to HTTP.

Review is split by layer (owner decision, 2026-10-08):
  * Facts derived only from the shared regulatory library (requirements,
    instrument relationships, applicability, effective dates) are confirmed by
    the Iroko team: superadmins.
  * A workspace's own rows (controls, evidence links, mappings, applicability
    decisions, owners) are confirmed by that workspace's admins.
  * Library-layer facts from a regulation a workspace uploaded privately are
    reviewed by that workspace's admins.

Roles are global in this codebase, so "workspace admin" means role admin (or
superadmin) AND membership of that workspace.
"""

from __future__ import annotations

from ingestion.models import DocumentAccess

from services.compliance_graph.visibility import Scope

PROPOSER_ROLES = {"superadmin", "admin", "analyst"}
ADMIN_ROLES = {"superadmin", "admin"}


class GraphError(Exception):
    status = 400


class GraphPermissionError(GraphError):
    status = 403


class GraphNotFound(GraphError):
    status = 404


class GraphConflict(GraphError):
    status = 409


class GraphInvalid(GraphError):
    status = 422


def can_propose(scope: Scope) -> bool:
    return scope.role in PROPOSER_ROLES


def is_workspace_admin(scope: Scope, workspace_id: str | None) -> bool:
    return scope.role in ADMIN_ROLES and bool(workspace_id) and scope.workspace_id == workspace_id


def library_review_owner(db, document_ids) -> str | None:
    """None when every document is shared (superadmins review); else the owning workspace.

    Raises when the documents belong to different private workspaces: such a
    row should never exist.
    """
    ids = [d for d in dict.fromkeys(document_ids or ()) if d]
    if not ids:
        return None
    rows = db.query(DocumentAccess).filter(DocumentAccess.document_id.in_(ids)).all()
    if len(rows) != len(ids):
        raise GraphNotFound("A source document of this item is not available")
    private = {r.workspace_id for r in rows if not r.shared_regulatory}
    if len(private) > 1:
        raise GraphConflict("This item spans private documents of different workspaces")
    return next(iter(private), None)


def can_review_library(db, scope: Scope, document_ids) -> bool:
    owner = library_review_owner(db, document_ids)
    if owner is None:
        return scope.is_superadmin
    return is_workspace_admin(scope, owner)


def require_library_reviewer(db, scope: Scope, document_ids) -> None:
    if not can_review_library(db, scope, document_ids):
        if library_review_owner(db, document_ids) is None:
            raise GraphPermissionError("Shared regulation facts are confirmed by the Iroko team")
        raise GraphPermissionError("Only an admin of this workspace can confirm this")


def require_workspace_admin(scope: Scope, workspace_id: str | None) -> None:
    if not is_workspace_admin(scope, workspace_id):
        raise GraphPermissionError("Only an admin of this workspace can do this")


def require_proposer(scope: Scope) -> None:
    if not can_propose(scope):
        raise GraphPermissionError("Your role can view these records but not change them")


def require_member(db, scope: Scope, user_id: str | None) -> None:
    """Owners must belong to the same workspace."""
    if not user_id:
        return
    from services.compliance_graph.visibility import workspace_of
    from models.database import User

    user = db.get(User, user_id)
    if not user or not user.is_active or workspace_of(db, user_id) != scope.workspace_id:
        raise GraphInvalid("The owner must be an active member of this workspace")
