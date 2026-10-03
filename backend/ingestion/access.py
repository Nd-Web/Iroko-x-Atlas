"""Fail-closed document permissions. Profile labels never establish membership."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy import and_, exists, or_, select

from ingestion.db import prepare_session, source_lock
from ingestion.models import DocumentAccess, Membership, Revision, Workspace
from ingestion.retired_demo import RETIRED_DOCUMENT_IDS
from models.database import Document, User


@dataclass(frozen=True)
class Principal:
    id: str
    role: str


principal = ContextVar("document_principal", default=None)


@contextmanager
def as_user(user):
    from ingestion.record_access import install_access_handlers

    install_access_handlers()
    token = principal.set(Principal(user.id, user.role))
    try:
        yield
    finally:
        principal.reset(token)


def workspace_id(db, user_id):
    prepare_session(db)
    member = db.get(Membership, user_id)
    return member.workspace_id if member else f"user:{user_id}"


def ensure_workspace(db, user_id):
    prepare_session(db)
    if not db.get(User, user_id):
        raise ValueError("Document owner does not exist")
    source_lock(db, f"workspace-user:{user_id}")
    member = db.get(Membership, user_id)
    if member:
        return member.workspace_id
    key = f"user:{user_id}"
    if not db.get(Workspace, key):
        db.add(Workspace(id=key, name="Private workspace"))
    db.add(Membership(user_id=user_id, workspace_id=key))
    db.flush()
    return key


def document_predicate(db, user=None, *, write=False):
    user = user or principal.get()
    if user is None:
        return Document.id.in_([])
    key = workspace_id(db, user.id)
    access_exists = exists(
        select(DocumentAccess.document_id).where(DocumentAccess.document_id == Document.id)
    )
    own = exists(
        select(DocumentAccess.document_id).where(
            DocumentAccess.document_id == Document.id,
            DocumentAccess.workspace_id == key,
            DocumentAccess.shared_regulatory.is_(False) if write else True,
        )
    )
    shared = exists(
        select(DocumentAccess.document_id).where(
            DocumentAccess.document_id == Document.id,
            DocumentAccess.shared_regulatory.is_(True),
        )
    )
    legacy = and_(~access_exists, Document.uploaded_by_id == user.id)
    retired = and_(
        Document.id.in_(RETIRED_DOCUMENT_IDS),
        Document.blob_url.is_(None),
        Document.source_connector_id.is_(None),
        ~exists(select(Revision.id).where(Revision.id == Document.id)),
    )
    return and_(
        ~retired, or_(own, legacy, shared if not write or user.role == "superadmin" else False)
    )


def require_document(db, document_id, user=None, *, write=False):
    from fastapi import HTTPException

    doc = (
        db.query(Document)
        .filter(Document.id == document_id, document_predicate(db, user, write=write))
        .first()
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


def allowed_document_ids(db, ids=None, user=None):
    query = db.query(Document.id).filter(document_predicate(db, user))
    if ids is not None:
        query = query.filter(Document.id.in_(ids))
    return {row[0] for row in query}


def search_filter():
    """Authoritative pre-filter prevents foreign content reaching any reranker."""
    from ingestion.db import Session

    if principal.get() is None:
        return None
    with Session() as db:
        ids = sorted(allowed_document_ids(db))
    if not ids:
        return None
    if len(ids) > 10000:
        raise RuntimeError("Document ACL exceeds search adapter limit; partition the index")
    if any("|" in x for x in ids):
        raise RuntimeError("Invalid document identity")
    safe = "|".join(x.replace("'", "''") for x in ids)
    return f"search.in(doc_id, '{safe}', '|')"
