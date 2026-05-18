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
from services.document_processor import process_document
from services.blob_storage import upload_document as upload_to_blob
from services.cosmos_graph import upsert_document_node
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
    query = db.query(Document)

    if department:
        query = query.filter(Document.department == department)
    if doc_type:
        query = query.filter(Document.file_type == doc_type)
    if status:
        query = query.filter(Document.status == status)

    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return DocumentListResponse(documents=docs, total=total)


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document for indexing.
    Supports PDF, DOCX, XLSX, TXT, CSV.
    """
    # Validate file type
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_TYPES)}",
        )

    # Read file
    content = await file.read()
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

    # Create document record
    document = Document(
        id=doc_id,
        title=title or filename.rsplit(".", 1)[0],
        filename=filename,
        file_type=ext,
        file_size=len(content),
        department=department,
        tags=json.loads(tags) if tags else [],
        status="processing",
        uploaded_by_id=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # ── Upload original file to Blob Storage ─────────────────────────────
    content_type_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "txt": "text/plain",
        "csv": "text/csv",
        "md": "text/markdown",
    }
    blob_url = await upload_to_blob(
        file_path=file_path,
        document_id=doc_id,
        filename=filename,
        content_type=content_type_map.get(ext, "application/octet-stream"),
    )
    if blob_url:
        document.blob_url = blob_url

    # ── Process: extract → chunk → embed → index ──────────────────────────
    try:
        result = await process_document(
            file_path=file_path,
            document_id=doc_id,
            title=document.title,
            metadata={
                "department":     department or "",
                "doc_type":       doc_type or ext,
                "file_type":      ext,
                "source":         filename,
                "filename":       filename,
                "blob_url":       blob_url or "",
                "classification": "internal",
                "language":       "en",
                "region":         "",
            },
        )

        document.status = "indexed" if result["success"] else "failed"
        document.chunk_count = result.get("chunk_count", 0)
        if not result["success"]:
            document.error_message = result.get("error", "Unknown error")

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        logger.error(f"Document processing error: {e}")

    finally:
        try:
            os.remove(file_path)
        except Exception:
            pass

    # ── Write document vertex to knowledge graph ──────────────────────────
    if document.status == "indexed":
        upsert_document_node(
            document_id=doc_id,
            title=document.title,
            doc_type=doc_type or ext,
            department=department or "",
            blob_url=blob_url or "",
        )

    db.add(AuditLog(
        user_id=current_user.id,
        action="document_uploaded",
        resource=f"documents/{doc_id}",
        details={"filename": filename, "title": document.title, "department": department or ""},
    ))
    db.commit()
    db.refresh(document)
    return document


@router.post("/upload", response_model=DocumentResponse)
async def upload_document_alias(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
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
        current_user=current_user,
        db=db,
    )


# ── Search endpoints (must come before /{document_id} to avoid path clash) ───

def _enrich_hits_with_blob_url(hits: list, db: Session) -> list:
    """Look up blob_url for each hit's doc_id and attach it."""
    doc_ids = list({h["doc_id"] for h in hits if h.get("doc_id")})
    if not doc_ids:
        return hits
    docs = db.query(Document.id, Document.blob_url).filter(Document.id.in_(doc_ids)).all()
    blob_map = {d.id: d.blob_url for d in docs}
    for h in hits:
        h["blob_url"] = blob_map.get(h.get("doc_id"))
    return hits


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
    ).one()
    total_documents, total_chunks, total_size_bytes = int(totals[0]), int(totals[1]), int(totals[2])

    # Status breakdown
    status_rows = db.query(Document.status, func.count(Document.id)).group_by(Document.status).all()
    status_counts = {status: cnt for status, cnt in status_rows}

    indexed_rate = round(status_counts.get("indexed", 0) / total_documents * 100, 1) if total_documents else 0.0

    # File type distribution
    by_file_type = [
        {"file_type": ft or "unknown", "count": cnt}
        for ft, cnt in db.query(Document.file_type, func.count(Document.id))
        .group_by(Document.file_type)
        .order_by(func.count(Document.id).desc())
        .all()
    ]

    # Department distribution
    by_department = [
        {"department": dept or "Unassigned", "count": cnt}
        for dept, cnt in db.query(Document.department, func.count(Document.id))
        .group_by(Document.department)
        .order_by(func.count(Document.id).desc())
        .all()
    ]

    # Upload trend — single query, grouped in Python
    trend_start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    uploads_in_range = db.query(Document.created_at).filter(Document.created_at >= trend_start).all()
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
        .filter(Document.status == "failed")
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
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


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
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.blob_url:
        raise HTTPException(status_code=422, detail="Document has no blob — cannot reindex")

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

    if doc.status == "indexed":
        upsert_document_node(
            document_id=document_id,
            title=doc.title,
            doc_type=doc.file_type,
            department=doc.department or "",
            blob_url=doc.blob_url or "",
        )

    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(require_role("superadmin", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted", "document_id": document_id}
