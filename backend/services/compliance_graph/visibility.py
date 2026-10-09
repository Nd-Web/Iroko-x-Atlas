"""
Who may see which graph rows: the only place this is decided.

A Scope is a workspace. API requests derive it from the signed-in user's
membership; the worker, which has no user, names the workspace directly. Both
see the same documents: those owned by the workspace plus the shared
regulatory library (ingestion.access.document_predicate's rule for pipeline
documents; graph rows only exist for pipeline documents).

Everything is expressed as SQL so filtering, counting and pagination happen in
the database and a count can never include a row the reader may not open.

"Current for a workspace": a document version is current for a workspace when
it is indexed and current, or when it was superseded by a newer version that
the workspace cannot see yet (a new version of a shared circular starts
unshared). Views label that case "a newer version is awaiting publication".
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased

from ingestion.models import DocumentAccess, Membership, Revision
from models.database import Document

LIVE_STATUSES = ("indexed", "superseded")


@dataclass(frozen=True)
class Scope:
    workspace_id: str
    user_id: str | None = None
    role: str | None = None

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"

    @property
    def is_admin(self) -> bool:
        return self.role in {"admin", "superadmin"}


def workspace_of(db, user_id: str) -> str:
    from ingestion.db import prepare_session

    prepare_session(db)
    member = db.get(Membership, user_id)
    return member.workspace_id if member else f"user:{user_id}"


def for_user(db, user) -> Scope:
    return Scope(workspace_of(db, user.id), user.id, user.role)


def for_workspace(workspace_id: str) -> Scope:
    return Scope(workspace_id)


def _access(scope: Scope, access):
    return or_(access.workspace_id == scope.workspace_id, access.shared_regulatory.is_(True))


def document_visible(scope: Scope, document_id_col, *, current: bool = True):
    """SQL: the document behind document_id_col is visible to scope.

    current=True requires the version to be current for the workspace;
    current=False accepts any published version (history views).
    """
    doc, rev, acc = aliased(Document), aliased(Revision), aliased(DocumentAccess)
    conditions = [
        doc.id == document_id_col,
        rev.id == doc.id,
        acc.document_id == doc.id,
        _access(scope, acc),
    ]
    if current:
        conditions.append(_current(scope, doc, rev))
    else:
        conditions.append(doc.status.in_(LIVE_STATUSES))
    return exists(select(doc.id).where(*conditions))


def _current(scope: Scope, doc, rev):
    newer_doc, newer_rev, newer_acc = aliased(Document), aliased(Revision), aliased(DocumentAccess)
    newer_visible = exists(
        select(newer_rev.id).where(
            newer_rev.source_key == rev.source_key,
            newer_rev.created_at > rev.created_at,
            newer_doc.id == newer_rev.id,
            newer_doc.status.in_(LIVE_STATUSES),
            newer_acc.document_id == newer_rev.id,
            _access(scope, newer_acc),
        )
    )
    return or_(
        and_(doc.status == "indexed", rev.is_current.is_(True)),
        and_(doc.status == "superseded", ~newer_visible),
    )


def visible_document_ids(db, scope: Scope, *, current: bool = True, ids=None) -> set[str]:
    query = db.query(Document.id).filter(document_visible(scope, Document.id, current=current))
    if ids is not None:
        ids = list(ids)
        if not ids:
            return set()
        query = query.filter(Document.id.in_(ids))
    return {row[0] for row in query}


def is_document_visible(db, scope: Scope, document_id: str, *, current: bool = True) -> bool:
    return bool(document_id) and document_id in visible_document_ids(db, scope, current=current, ids=[document_id])


def awaiting_publication(db, scope: Scope, document_id: str) -> bool:
    """True when a newer version of this document exists that scope cannot see yet."""
    doc = db.get(Document, document_id)
    rev = db.get(Revision, document_id)
    if not doc or not rev or doc.status != "superseded":
        return False
    newer = (
        db.query(Revision.id)
        .filter(Revision.source_key == rev.source_key, Revision.created_at > rev.created_at)
        .all()
    )
    return bool(newer) and not visible_document_ids(db, scope, current=False, ids=[r[0] for r in newer])


def obligation_visible(scope: Scope, obligation_model, *, current: bool = True):
    return and_(
        obligation_model.status == "active",
        document_visible(scope, obligation_model.document_id, current=current),
    )


def lineage_visible(scope: Scope, lineage_col):
    """Some published version of the requirement lineage is visible to scope."""
    from models.compliance_graph import Obligation

    member = aliased(Obligation)
    return exists(
        select(member.id).where(
            member.lineage_id == lineage_col,
            document_visible(scope, member.document_id, current=False),
        )
    )


def link_visible(scope: Scope, link_model):
    """Library links: every document they touch is visible. Workspace links: also ours."""
    endpoint_ok = []
    for kind_col, id_col, doc_col in (
        (link_model.from_type, link_model.from_id, link_model.from_document_id),
        (link_model.to_type, link_model.to_id, link_model.to_document_id),
    ):
        endpoint_ok.append(
            or_(
                # Requirement lineages: some published version must be visible.
                and_(kind_col == "obligation", lineage_visible(scope, id_col)),
                # Categories, returns, Acts and external references carry no document.
                and_(kind_col.in_(("category", "return", "act", "reference")), doc_col.is_(None)),
                # Controls are workspace rows; their document (if any) must be visible.
                and_(kind_col == "control", or_(doc_col.is_(None), document_visible(scope, doc_col, current=False))),
                and_(kind_col == "document", document_visible(scope, doc_col, current=False)),
            )
        )
    return and_(
        link_model.status == "active",
        or_(link_model.workspace_id.is_(None), link_model.workspace_id == scope.workspace_id),
        *endpoint_ok,
    )


def control_visible(scope: Scope, control_model):
    return and_(
        control_model.workspace_id == scope.workspace_id,
        or_(control_model.document_id.is_(None),
            document_visible(scope, control_model.document_id, current=False)),
    )
