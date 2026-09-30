"""Authenticated operation and evidence review using existing Iroko roles."""

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func

from ingestion.db import prepare_session
from ingestion.models import Chunk, CrawlRun, Job, Page, Revision, Source
from ingestion.pipeline import reindex, reprocess, review
from ingestion.queue import enqueue
from ingestion.sources import DOMAINS, official_url
from models.database import Document, get_db
from services.auth_utils import get_current_user, require_role

router = APIRouter(prefix="/api/ingestion", tags=["Document ingestion"])
admin = require_role("admin", "superadmin")


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
    return {
        "jobs": dict(db.query(Job.state, func.count()).group_by(Job.state).all()),
        "awaiting_review": db.query(Revision).filter_by(review_status="required").count(),
    }


@router.get("/reviews")
def reviews(user=Depends(admin), db=Depends(session)):
    return [
        {"id": r.id, "issues": r.issues, "provenance": r.provenance}
        for r in db.query(Revision).filter_by(review_status="required").limit(100)
    ]


@router.get("/runs")
def runs(user=Depends(admin), db=Depends(session)):
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
    revision = db.get(Revision, document_id)
    if not revision or not db.get(Document, document_id):
        raise HTTPException(404, "Document pipeline record not found")
    pages = db.query(Page).filter_by(document_id=document_id).order_by(Page.position).all()
    job = db.get(Job, f"document:{document_id}")
    return {
        "id": revision.id,
        "sha256": revision.sha256,
        "previous_id": revision.previous_id,
        "is_current": revision.is_current,
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
async def original(document_id: str, user=Depends(get_current_user), db=Depends(session)):
    from services.blob_storage import download_document

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
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
    try:
        review(db, document_id, user.id, body.decision, body.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "accepted"}


@router.post("/documents/{document_id}/reprocess")
def reprocess_document(document_id: str, user=Depends(admin), db=Depends(session)):
    try:
        reprocess(db, document_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "queued"}


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str, user=Depends(admin), db=Depends(session)):
    try:
        reindex(db, document_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "queued"}


@router.get("/sources")
def sources(user=Depends(admin), db=Depends(session)):
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
            "result": s.result,
        }
        for s in db.query(Source).all()
    ]


@router.post("/sources")
def create_source(body: SourceRequest, user=Depends(admin), db=Depends(session)):
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


@router.post("/sources/{source_id}/run")
def run_source(source_id: str, user=Depends(admin), db=Depends(session)):
    source = db.get(Source, source_id)
    if not source or not source.enabled:
        raise HTTPException(409, "Enable the source before running it")
    enqueue(db, "source", source_id)
    db.commit()
    return {"status": "queued"}


@router.patch("/sources/{source_id}")
def update_source(source_id: str, body: SourceRequest, user=Depends(admin), db=Depends(session)):
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
