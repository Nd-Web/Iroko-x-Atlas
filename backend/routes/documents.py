"""
Documents Route — Upload, manage, and query enterprise documents.
"""
import os
import json
import logging
import aiofiles
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from models.database import get_db, User, Document, AuditLog
from models.schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentAnalyticsResponse,
    DocumentStatusBreakdown,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSearchHit,
)
from services.auth_utils import get_current_user, require_role
from ingestion.access import document_predicate, require_document
from ingestion.validation import UploadLimitError
from services.document_processor import process_document
from services.azure_search import search_documents as azure_search_documents

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"pdf", "docx", "xlsx", "txt", "md", "csv"}
MAX_FILE_SIZE_MB = 50
UPLOAD_DIR = "/tmp/atlas_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    department: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all uploaded documents with optional filters."""
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(422, "Invalid pagination")
    query = db.query(Document).filter(document_predicate(db, current_user))

    if department:
        query = query.filter(Document.department == department)
    if doc_type:
        query = query.filter(Document.file_type == doc_type)
    if status:
        query = query.filter(Document.status == status)
    else:
        # Archived and superseded revisions are retained for audit but are not
        # part of the live library unless explicitly requested.
        query = query.filter(Document.status.notin_(["archived", "superseded"]))

    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return DocumentListResponse(documents=docs, total=total)


DOCUMENT_ROLES = {"regulation", "policy", "procedure", "evidence_record", "other"}


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    document_role: Optional[str] = Form(None),
    replaces_document_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document for indexing through the durable ingestion pipeline.
    Supports PDF, DOCX, XLSX, TXT, CSV, MD.

    document_role answers "what is this document?" for the compliance graph:
    regulation | policy | procedure | evidence_record | other.
    replaces_document_id makes the upload a new version of a document you can
    edit (for example a renamed policy), so its history and links carry over.
    """
    from ingestion.queue import enabled
    if current_user.role not in {"superadmin", "admin", "analyst"}:
        raise HTTPException(403, "Document upload is not permitted for this role")
    if not enabled():
        raise HTTPException(503, "Document ingestion is unavailable; please try again later")
    role = (document_role or "").strip().lower() or None
    if role is not None and role not in DOCUMENT_ROLES:
        raise HTTPException(422, f"document_role must be one of: {', '.join(sorted(DOCUMENT_ROLES))}")
    source_key = None
    if replaces_document_id:
        from ingestion.db import prepare_session
        from ingestion.models import Revision
        replaced = require_document(db, replaces_document_id, current_user, write=True)
        prepare_session(db)
        revision = db.get(Revision, replaced.id)
        if revision is None:
            raise HTTPException(409, "That document predates the ingestion pipeline and cannot be versioned")
        source_key = revision.source_key
    # Validate file type
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_TYPES)}",
        )

    # Read file
    content = await file.read(MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Maximum: {MAX_FILE_SIZE_MB}MB",
        )

    # Save to disk temporarily
    from models.database import generate_id
    doc_id = generate_id()
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{ext}")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    from ingestion.pipeline import accept
    try:
        parsed_tags = json.loads(tags or "[]")
        if not isinstance(parsed_tags, list) or not all(isinstance(t, str) for t in parsed_tags):
            raise ValueError("Tags must be a list of strings")
        metadata = {"department": department, "doc_type": doc_type or ext,
                    "tags": parsed_tags, "classification": "internal"}
        if role:
            metadata["document_role"] = role
        return await accept(db, file_path, filename, title, current_user.id, metadata,
                            source_key=source_key)
    except UploadLimitError as exc:
        db.rollback()
        raise HTTPException(429, str(exc), headers={"Retry-After": "3600"}) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Could not durably accept document")
        raise HTTPException(503, "Document could not be saved. Please retry; processing has not been accepted.") from exc
    finally:
        os.remove(file_path)


@router.post("/upload", response_model=DocumentResponse)
async def upload_document_alias(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    document_role: Optional[str] = Form(None),
    replaces_document_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias for POST /api/documents — same handler, alternate path."""
    return await upload_document(
        file=file,
        title=title,
        department=department,
        doc_type=doc_type,
        tags=tags,
        document_role=document_role,
        replaces_document_id=replaces_document_id,
        current_user=current_user,
        db=db,
    )


# ── Search endpoints (must come before /{document_id} to avoid path clash) ───

def _enrich_hits_with_blob_url(hits: list, db: Session) -> list:
    """Look up blob_url for each hit's doc_id and attach it."""
    doc_ids = list({h["doc_id"] for h in hits if h.get("doc_id")})
    if not doc_ids:
        return hits
    docs = db.query(Document.id, Document.blob_url).filter(Document.id.in_(doc_ids), document_predicate(db)).all()
    blob_map = {d.id: d.blob_url for d in docs}
    for h in hits:
        h["blob_url"] = blob_map.get(h.get("doc_id"))
    return [h for h in hits if h.get("doc_id") in blob_map]


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents_get(
    q: str,
    top: int = 10,
    department: Optional[str] = None,
    doc_type: Optional[str] = None,
    language: Optional[str] = None,
    classification: Optional[str] = None,
    source: Optional[str] = None,
    rerank: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search documents using Azure AI Search (hybrid BM25 + vector + semantic).

    - **q** — search query (required)
    - **top** — maximum results to return (1-50, default 10)
    - **department** — filter by department
    - **doc_type** — filter by file type (pdf, docx, txt, …)
    - **language** — filter by language code (e.g. `en`)
    - **classification** — filter by classification level
    - **source** — filter by source filename (exact match)
    - **rerank** — apply Cohere reranking (default true)
    """
    if top < 1 or top > 50:
        raise HTTPException(status_code=422, detail="'top' must be between 1 and 50")

    result = await azure_search_documents(
        query=q,
        top=top,
        department=department,
        doc_type=doc_type,
        language=language,
        classification=classification,
        source=source,
        apply_rerank=rerank,
    )

    enriched = _enrich_hits_with_blob_url(result["results"], db)
    hits = [DocumentSearchHit(**h) for h in enriched]
    return DocumentSearchResponse(
        query=q,
        total_hits=result["total_hits"],
        results=hits,
        knowledge_gap=result["knowledge_gap"],
        confidence=result["confidence"],
    )


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents_post(
    body: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search documents using Azure AI Search — richer body version.

    Accepts the same parameters as the GET endpoint but as a JSON body,
    which is more convenient for complex filter combinations.
    """
    result = await azure_search_documents(
        query=body.query,
        top=body.top,
        department=body.department,
        doc_type=body.doc_type,
        language=body.language,
        classification=body.classification,
        source=body.source,
        apply_rerank=body.rerank,
    )

    enriched = _enrich_hits_with_blob_url(result["results"], db)
    hits = [DocumentSearchHit(**h) for h in enriched]
    return DocumentSearchResponse(
        query=body.query,
        total_hits=result["total_hits"],
        results=hits,
        knowledge_gap=result["knowledge_gap"],
        confidence=result["confidence"],
    )


@router.get("/analytics", response_model=DocumentAnalyticsResponse)
async def get_document_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Document-level analytics for the admin dashboard.

    - **days** — upload trend window in days (1-90, default 30)
    """
    if days < 1 or days > 90:
        raise HTTPException(status_code=422, detail="'days' must be between 1 and 90")

    now = datetime.utcnow()

    # Aggregate totals in a single pass
    totals = db.query(
        func.count(Document.id),
        func.coalesce(func.sum(Document.chunk_count), 0),
        func.coalesce(func.sum(Document.file_size), 0),
    ).filter(document_predicate(db, current_user)).one()
    total_documents, total_chunks, total_size_bytes = int(totals[0]), int(totals[1]), int(totals[2])

    # Status breakdown
    status_rows = db.query(Document.status, func.count(Document.id)).filter(document_predicate(db, current_user)).group_by(Document.status).all()
    status_counts = {status: cnt for status, cnt in status_rows}

    indexed_rate = round(status_counts.get("indexed", 0) / total_documents * 100, 1) if total_documents else 0.0

    # File type distribution
    by_file_type = [
        {"file_type": ft or "unknown", "count": cnt}
        for ft, cnt in db.query(Document.file_type, func.count(Document.id))
        .filter(document_predicate(db, current_user))
        .group_by(Document.file_type)
        .order_by(func.count(Document.id).desc())
        .all()
    ]

    # Department distribution
    by_department = [
        {"department": dept or "Unassigned", "count": cnt}
        for dept, cnt in db.query(Document.department, func.count(Document.id))
        .filter(document_predicate(db, current_user))
        .group_by(Document.department)
        .order_by(func.count(Document.id).desc())
        .all()
    ]

    # Upload trend — single query, grouped in Python
    trend_start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    uploads_in_range = db.query(Document.created_at).filter(Document.created_at >= trend_start, document_predicate(db, current_user)).all()
    daily_counts: dict = defaultdict(int)
    for (ts,) in uploads_in_range:
        daily_counts[ts.strftime("%Y-%m-%d")] += 1

    upload_trend = [
        {
            "date": (trend_start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "count": daily_counts.get((trend_start + timedelta(days=i)).strftime("%Y-%m-%d"), 0),
        }
        for i in range(days)
    ]

    # Failed documents (up to 10 most recent)
    failed_docs = (
        db.query(Document)
        .filter(Document.status == "failed", document_predicate(db, current_user))
        .order_by(Document.created_at.desc())
        .limit(10)
        .all()
    )

    return DocumentAnalyticsResponse(
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_size_bytes=total_size_bytes,
        indexed_rate=indexed_rate,
        status_breakdown=DocumentStatusBreakdown(
            indexed=status_counts.get("indexed", 0),
            processing=status_counts.get("processing", 0),
            failed=status_counts.get("failed", 0),
            pending=status_counts.get("pending", 0),
            review_required=status_counts.get("review_required", 0),
            rejected=status_counts.get("rejected", 0),
            superseded=status_counts.get("superseded", 0),
            archived=status_counts.get("archived", 0),
        ),
        by_file_type=by_file_type,
        by_department=by_department,
        upload_trend=upload_trend,
        failed_documents=[
            {
                "id": d.id,
                "title": d.title,
                "filename": d.filename,
                "error_message": d.error_message,
                "created_at": d.created_at.isoformat(),
            }
            for d in failed_docs
        ],
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_document(db, document_id, current_user)


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    document_id: str,
    current_user: User = Depends(require_role("superadmin", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    """
    Re-run the full extraction → chunking → embedding → Azure Search pipeline
    for a document already stored in blob storage. Useful for fixing documents
    stuck in 'processing' or 'failed' state.
    """
    doc = require_document(db, document_id, current_user, write=True)
    if not doc.blob_url:
        raise HTTPException(status_code=422, detail="Document has no blob — cannot reindex")

    from ingestion.queue import enabled
    if enabled() and (doc.extra_metadata or {}).get("pipeline"):
        from ingestion.pipeline import reprocess
        try:
            reprocess(db, document_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        db.refresh(doc)
        return doc

    from services.blob_storage import download_document as download_blob
    import tempfile

    dest_path = os.path.join(UPLOAD_DIR, f"{document_id}_reindex.{doc.file_type}")
    ok = await download_blob(document_id, doc.filename, dest_path)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to download document from blob storage")

    doc.status = "processing"
    db.commit()

    try:
        result = await process_document(
            file_path=dest_path,
            document_id=document_id,
            title=doc.title,
            metadata={
                "department": doc.department or "",
                "doc_type": doc.file_type,
                "file_type": doc.file_type,
                "source": doc.filename,
                "filename": doc.filename,
                "blob_url": doc.blob_url or "",
                "classification": "internal",
                "language": "en",
                "region": "",
            },
        )
        doc.status = "indexed" if result["success"] else "failed"
        doc.chunk_count = result.get("chunk_count", 0)
        doc.error_message = None if result["success"] else result.get("error", "Unknown error")
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        logger.error(f"Reindex error for '{doc.title}': {e}")
    finally:
        try:
            os.remove(dest_path)
        except Exception:
            pass

    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(require_role("superadmin", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    doc = require_document(db, document_id, current_user, write=True)
    from ingestion.queue import enabled
    is_pipeline = bool((doc.extra_metadata or {}).get("pipeline"))
    if is_pipeline and not enabled():
        # Hard-deleting here would orphan the revision, pages and audit trail.
        raise HTTPException(503, "Document pipeline is not enabled; pipeline documents can only be archived once it is")
    if is_pipeline:
        from ingestion.db import prepare_session
        from ingestion.models import Job, Revision
        prepare_session(db)
        job = db.query(Job).filter_by(id=f"document:{document_id}").with_for_update().first()
        if job and job.state == "running":
            raise HTTPException(409, "Document is processing; wait until it finishes before archiving")
        if job:
            job.state = "cancelled"
        graph_job = db.query(Job).filter_by(id=f"graph:{document_id}").with_for_update().first()
        if graph_job and graph_job.state in {"queued", "retry"}:
            graph_job.state = "cancelled"
        revision = db.get(Revision, document_id)
        if revision:
            revision.is_current = False
        doc.status = "archived"
        # Graph rows are read-gated, never deleted; affected workspaces re-sync so
        # links that relied on this document are flagged "source no longer available".
        from services.compliance_graph.triggers import after_document_change
        after_document_change(db, document_id)
        db.commit()
        return {"message": "Document archived; original and audit history retained", "document_id": document_id}
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted", "document_id": document_id}
