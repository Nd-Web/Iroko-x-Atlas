"""Authenticated operation and evidence review using existing Iroko roles."""

import asyncio
import logging
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func

from ingestion.access import document_predicate, require_document
from ingestion.db import prepare_session
from ingestion.models import Chunk, CrawlRun, DocumentAccess, Job, Page, Revision, Source
from ingestion.pipeline import reindex, reprocess, review
from ingestion.queue import enqueue
from ingestion.sources import DOMAINS, official_url
from models.database import Document, get_db
from services.auth_utils import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingestion", tags=["Document ingestion"])
admin = require_role("admin", "superadmin")
platform_admin = require_role("superadmin")


def session(db=Depends(get_db)):
    from ingestion.queue import enabled

    if not enabled():
        raise HTTPException(
            503, "Document pipeline is not enabled; complete its deployment setup first"
        )
    prepare_session(db)
    return db


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(min_length=5, max_length=2000)
    # The reviewer can record a publication date read from the document itself.
    published_date: date | None = None


class WorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class MemberRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)


class SharingRequest(BaseModel):
    shared_regulatory: bool
    note: str = Field(min_length=10, max_length=2000)


@router.post("/workspaces")
def create_workspace(body: WorkspaceRequest, user=Depends(platform_admin), db=Depends(session)):
    from ingestion.models import Workspace
    from models.database import AuditLog

    workspace = Workspace(name=body.name)
    db.add(workspace)
    db.flush()
    db.add(
        AuditLog(user_id=user.id, action="workspace_created", resource=f"workspaces/{workspace.id}")
    )
    db.commit()
    return {"id": workspace.id, "name": workspace.name}


@router.post("/workspaces/{workspace_id}/members")
def add_member(
    workspace_id: str, body: MemberRequest, user=Depends(platform_admin), db=Depends(session)
):
    from ingestion.workspaces import assign_member

    assign_member(db, user, body.user_id, workspace_id)
    return {"status": "assigned"}


@router.put("/documents/{document_id}/sharing")
def share_document(
    document_id: str, body: SharingRequest, user=Depends(platform_admin), db=Depends(session)
):
    from ingestion.workspaces import set_shared
    from services.compliance_graph.triggers import after_sharing_change

    set_shared(db, user, document_id, body.shared_regulatory, body.note)
    # Every graph workspace may have gained or lost this document's requirements.
    after_sharing_change(db, document_id)
    db.commit()
    return {"shared_regulatory": body.shared_regulatory}


class SourceRequest(BaseModel):
    regulator: str
    url: str = Field(max_length=2048)
    parser: str = Field(pattern="^(cbn_json|html_links)$")
    enabled: bool = False
    interval_hours: int = Field(0, ge=0, le=720)
    max_documents: int = Field(20, ge=1, le=100)

    @field_validator("interval_hours")
    @classmethod
    def manual_or_recurring(cls, value):
        if 0 < value < 6:
            raise ValueError("Use 0 for manual collection or at least 6 hours for recurrence")
        return value


@router.get("/stats")
def stats(user=Depends(admin), db=Depends(session)):
    ids = db.query(Document.id).filter(document_predicate(db, user, write=True))
    return {
        "jobs": dict(
            db.query(Job.state, func.count())
            .filter(Job.kind == "document", Job.target_id.in_(ids))
            .group_by(Job.state)
            .all()
        ),
        "awaiting_review": db.query(Revision)
        .filter(Revision.id.in_(ids), Revision.review_status == "required")
        .count(),
    }


@router.get("/reviews")
def reviews(user=Depends(admin), db=Depends(session)):
    return [
        {"id": r.id, "issues": r.issues, "provenance": r.provenance}
        for r in db.query(Revision)
        .filter(
            Revision.review_status == "required",
            Revision.id.in_(db.query(Document.id).filter(document_predicate(db, user, write=True))),
        )
        .limit(100)
    ]


@router.get("/runs")
def runs(user=Depends(platform_admin), db=Depends(session)):
    return [
        {
            "id": r.id,
            "source_id": r.source_id,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "result": r.result,
        }
        for r in db.query(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(100)
    ]


@router.get("/documents/{document_id}")
def detail(document_id: str, user=Depends(get_current_user), db=Depends(session)):
    require_document(db, document_id, user)
    revision = db.get(Revision, document_id)
    doc = db.get(Document, document_id)
    if not revision or not doc:
        raise HTTPException(404, "Document pipeline record not found")
    pages = db.query(Page).filter_by(document_id=document_id).order_by(Page.position).all()
    job = db.get(Job, f"document:{document_id}")
    access = db.get(DocumentAccess, document_id)
    try:
        official_url(
            revision.provenance.get("source_url", ""), revision.provenance.get("regulator", "")
        )
        official = True
    except ValueError:
        official = False
    return {
        "id": revision.id,
        "sha256": revision.sha256,
        "previous_id": revision.previous_id,
        "is_current": revision.is_current,
        "shared_regulatory": bool(access and access.shared_regulatory),
        # Mirrors workspaces.set_shared: only current, indexed official evidence.
        "shareable": official and revision.is_current and doc.status == "indexed",
        "provenance": revision.provenance,
        "extraction": revision.extraction,
        "issues": revision.issues,
        "review_status": revision.review_status,
        "review_note": revision.review_note,
        "job": {"state": job.state, "attempts": job.attempts, "error": job.error} if job else None,
        "pages": [
            {
                "number": p.page_number,
                "locator": p.locator,
                "method": p.method,
                "quality": p.quality,
                "text": p.text,
            }
            for p in pages
        ],
        "chunks": [
            {"id": c.id, "content": c.content, **c.provenance}
            for c in db.query(Chunk).filter_by(document_id=document_id).order_by(Chunk.chunk_index)
        ],
    }


@router.get("/documents/{document_id}/original")
async def original(document_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    # Originals live in Blob Storage, so downloading does not require the worker.
    from services.blob_storage import download_document

    prepare_session(db)
    doc = require_document(db, document_id, user)
    with tempfile.TemporaryDirectory(prefix="iroko-original-") as directory:
        path = str(Path(directory) / "original")
        ok = await asyncio.to_thread(
            lambda: asyncio.run(download_document(doc.id, doc.filename, path))
        )
        if not ok:
            raise HTTPException(502, "Original is temporarily unavailable")
        data = Path(path).read_bytes()
    from urllib.parse import quote

    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename)}",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/documents/{document_id}/review")
def review_document(
    document_id: str, body: ReviewRequest, user=Depends(admin), db=Depends(session)
):
    require_document(db, document_id, user, write=True)
    try:
        review(db, document_id, user.id, body.decision, body.note, body.published_date)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "accepted"}


@router.post("/documents/{document_id}/reprocess")
def reprocess_document(document_id: str, user=Depends(admin), db=Depends(session)):
    require_document(db, document_id, user, write=True)
    try:
        reprocess(db, document_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "queued"}


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str, user=Depends(admin), db=Depends(session)):
    require_document(db, document_id, user, write=True)
    try:
        reindex(db, document_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "queued"}


@router.get("/sources")
def sources(user=Depends(platform_admin), db=Depends(session)):
    jobs = {j.target_id: j for j in db.query(Job).filter(Job.kind == "source")}

    def job_state(source_id):
        job = jobs.get(source_id)
        if job is None:
            return None
        return {
            "state": job.state,
            "attempts": job.attempts,
            "error": job.error,
            "available_at": job.available_at,
        }

    return [
        {
            "id": s.id,
            "regulator": s.regulator,
            "url": s.url,
            "enabled": s.enabled,
            "parser": s.parser,
            "interval_hours": s.interval_hours,
            "max_documents": s.max_documents,
            "last_run": s.last_run,
            "job": job_state(s.id),
            # Per-link backoff records are internal; expose only their count.
            "result": {
                **{k: v for k, v in (s.result or {}).items() if k != "failures"},
                "failing_links": len((s.result or {}).get("failures") or {}),
            },
        }
        for s in db.query(Source).order_by(Source.regulator, Source.url).all()
    ]


@router.post("/sources")
def create_source(body: SourceRequest, user=Depends(platform_admin), db=Depends(session)):
    if body.regulator not in DOMAINS or (body.parser == "cbn_json" and body.regulator != "CBN"):
        raise HTTPException(422, "Unsupported regulator/parser combination")
    try:
        url = official_url(body.url, body.regulator)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if db.query(Source).filter_by(url=url).first():
        raise HTTPException(409, "Source already registered")
    source = Source(**{**body.model_dump(), "url": url}, owner_id=user.id)
    db.add(source)
    db.commit()
    return {"id": source.id}


@router.post("/sources/{source_id}/import")
async def import_listed_document(
    source_id: str,
    source_url: str = Form(..., max_length=2048),
    file: UploadFile = File(...),
    user=Depends(platform_admin),
    db=Depends(session),
):
    """Accept a file an administrator downloaded from the regulator's official link.

    Only items from the source's latest listing are accepted, so provenance comes
    from the regulator's own catalogue. Where the catalogue states a file size,
    the upload must match it byte for byte.
    """
    import os

    from ingestion.sources import ATTACHMENT_TYPES, accept_listed, check_attachment
    from ingestion.validation import UploadLimitError
    from models.database import AuditLog

    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    listed = (source.result or {}).get("missing") or []
    item = next((i for i in listed if i.get("source_url") == source_url), None)
    if item is None:
        raise HTTPException(
            409, "That link is not in this source's latest list of missing documents. "
            "Run Collect now, then import it from the list.",
        )
    ext = Path(urlsplit(source_url).path).suffix.lower()
    if ext not in ATTACHMENT_TYPES:
        raise HTTPException(422, "Only PDF, DOCX and XLSX regulator files can be imported")
    limit = int(os.getenv("DOCUMENT_MAX_BYTES", str(50 * 1024 * 1024)))
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "File exceeds the document size limit")
    expected = item.get("catalogue_size")
    if expected and len(data) != expected:
        raise HTTPException(
            422,
            f"This file is {len(data):,} bytes but the regulator's catalogue lists "
            f"{expected:,} bytes. Download the original from the official link and try again.",
        )
    try:
        check_attachment(data, source_url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with tempfile.TemporaryDirectory(prefix="iroko-import-") as directory:
        path = Path(directory) / ("download" + ext)
        path.write_bytes(data)
        try:
            doc = await accept_listed(
                db,
                path,
                {k: v for k, v in item.items() if k != "importable"},
                source.owner_id,
                source.regulator,
                {"acquisition": "browser_download_import", "imported_by": user.id},
            )
        except UploadLimitError as exc:
            db.rollback()
            raise HTTPException(429, str(exc), headers={"Retry-After": "3600"}) from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Could not accept imported regulator file")
            raise HTTPException(
                503, "The file could not be saved. Please retry; it has not been accepted."
            ) from exc
    db.add(
        AuditLog(
            user_id=user.id,
            action="regulatory_document_imported",
            resource=f"documents/{doc.id}",
            details={"source_id": source.id, "source_url": source_url, "bytes": len(data)},
        )
    )
    source = db.get(Source, source_id)
    remaining = [i for i in (source.result or {}).get("missing") or [] if i["source_url"] != source_url]
    source.result = {
        **(source.result or {}),
        "missing": remaining,
        "missing_total": max(0, int((source.result or {}).get("missing_total", 0)) - 1),
    }
    db.commit()
    return {"document_id": doc.id, "status": doc.status}


@router.post("/sources/{source_id}/run")
def run_source(source_id: str, user=Depends(platform_admin), db=Depends(session)):
    source = db.get(Source, source_id)
    if not source or not source.enabled:
        raise HTTPException(409, "Enable the source before running it")
    enqueue(db, "source", source_id)
    db.commit()
    return {"status": "queued"}


@router.patch("/sources/{source_id}")
def update_source(
    source_id: str, body: SourceRequest, user=Depends(platform_admin), db=Depends(session)
):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if body.url != source.url or body.regulator != source.regulator or body.parser != source.parser:
        raise HTTPException(422, "Register a new source to change its identity")
    source.enabled, source.interval_hours, source.max_documents = (
        body.enabled,
        body.interval_hours,
        body.max_documents,
    )
    db.commit()
    return {"status": "updated"}
