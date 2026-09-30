"""Accept, process and review Iroko documents with durable checkpoints."""

import asyncio
import hashlib
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from ingestion import extraction
from ingestion.chunking import chunk_pages
from ingestion.db import prepare_session, source_lock
from ingestion.models import Chunk, Job, OcrBudget, Page, Revision
from ingestion.queue import enqueue, finish, owned
from ingestion.storage import preserve
from models.database import Alert, AuditLog, Document, generate_id

logger = logging.getLogger(__name__)


async def accept(
    db,
    path,
    filename,
    title,
    user_id,
    metadata=None,
    source_key=None,
    connector_id=None,
    source_item_id=None,
):
    """Commit Document, immutable revision and job together after preserving bytes."""
    prepare_session(db)
    metadata = dict(metadata or {})
    filename = Path(filename.replace("\\", "/")).name
    if not filename or len(filename) > 255:
        raise ValueError("Invalid filename")
    with Path(path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    source_key = source_key or f"upload:{user_id}:{filename}"
    source_lock(db, source_key)
    existing = db.query(Revision).filter_by(source_key=source_key, sha256=digest).first()
    if existing:
        document = db.get(Document, existing.id)
        if document is None:
            raise ValueError("Archived document; contact an administrator before restoring it")
        return document
    previous = (
        db.query(Revision)
        .filter_by(source_key=source_key)
        .order_by(Revision.created_at.desc())
        .first()
    )
    document_id = generate_id()
    blob_url = await preserve(path, document_id, filename)
    metadata.update(
        {
            "source": metadata.get("source_url") or filename,
            "file_type": filename.rsplit(".", 1)[-1].lower(),
            "filename": filename,
        }
    )
    doc = Document(
        id=document_id,
        title=title or filename,
        filename=filename,
        file_type=metadata["file_type"],
        file_size=Path(path).stat().st_size,
        department=metadata.get("department"),
        tags=metadata.get("tags", []),
        status="pending",
        blob_url=blob_url,
        uploaded_by_id=user_id,
        source_connector_id=connector_id,
        source_item_id=source_item_id,
        extra_metadata={"pipeline": "v1", "sha256": digest},
    )
    db.add(doc)
    db.add(
        Revision(
            id=document_id,
            source_key=source_key,
            sha256=digest,
            previous_id=previous.id if previous else None,
            provenance=metadata,
        )
    )
    enqueue(db, "document", document_id)
    db.add(
        AuditLog(
            user_id=user_id,
            action="document_queued",
            resource=f"documents/{document_id}",
            details={"sha256": digest, "previous_id": previous.id if previous else None},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prepare_session(db)
        duplicate = db.query(Revision).filter_by(source_key=source_key, sha256=digest).first()
        if not duplicate:
            raise
        # A concurrent upload won. The unused immutable blob can be cleaned by retention policy.
        return db.get(Document, duplicate.id)
    db.refresh(doc)
    return doc


def reserve_ocr(db, count):
    day = datetime.utcnow().date().isoformat()
    source_lock(db, f"ocr:{day}")
    budget = db.get(OcrBudget, day)
    if budget is None:
        budget = OcrBudget(day=day, pages=0)
        db.add(budget)
    allowed = min(
        count,
        max(0, int(os.getenv("DOCINTEL_DAILY_PAGE_BUDGET", "500")) - budget.pages),
        int(os.getenv("DOCINTEL_MAX_PAGES_PER_DOCUMENT", "50")),
    )
    budget.pages += allowed
    db.commit()  # Reserve before paid work, including failed calls.
    return allowed


async def process(db, key, token):
    job = owned(db, key, token)
    doc, revision = db.get(Document, job.target_id), db.get(Revision, job.target_id)
    if not doc or not revision:
        finish(db, key, token, state="cancelled")
        return
    if revision.review_status == "rejected":
        finish(db, key, token, state="rejected")
        return
    doc.status, doc.error_message = "processing", None
    document_id, filename, file_type = doc.id, doc.filename, doc.file_type
    db.commit()
    saved_pages = db.query(Page).filter_by(document_id=document_id).order_by(Page.position).all()
    if not saved_pages:
        from services.blob_storage import download_document

        with tempfile.TemporaryDirectory(prefix="iroko-document-") as directory:
            path = str(Path(directory) / f"original.{file_type}")
            # Existing blob adapter is synchronous internally; keep it out of the worker loop.
            ok = await asyncio.to_thread(
                lambda: asyncio.run(download_document(document_id, filename, path))
            )
            if not ok:
                raise RuntimeError("Could not read preserved original from Blob Storage")
            with open(path, "rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != revision.sha256:
                    raise ValueError("Original file checksum does not match its accepted revision")
            pages = await asyncio.to_thread(extraction.native_pages, path, file_type)
            flagged = [p for p in pages if file_type == "pdf" and extraction.needs_ocr(p)]
            if flagged:
                configured = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") and os.getenv(
                    "AZURE_DOCUMENT_INTELLIGENCE_KEY"
                )
                permitted = reserve_ocr(db, len(flagged)) if configured else 0
                numbers = [p["page_number"] for p in flagged[:permitted]]
                replacements = {}
                if numbers:
                    try:
                        replacements = await asyncio.to_thread(extraction.ocr_pages, path, numbers)
                    except Exception:
                        logger.exception("OCR failed for document %s", document_id)
                for item in flagged:
                    replacement = replacements.get(item["page_number"])
                    if replacement:
                        item.update(replacement)
                    else:
                        item["quality"]["pending_ocr"] = True
        owned(db, key, token)
        issues = extraction.extraction_issues(pages)
        if revision.previous_id:
            issues.append({"reasons": ["new_version_requires_review"]})
        if revision.provenance.get("regulator") and not revision.provenance.get("published_date"):
            issues.append({"reasons": ["publication_date_missing"]})
        if not pages:
            issues.append({"reasons": ["empty_document"]})
        for position, item in enumerate(pages):
            db.add(Page(document_id=document_id, position=position, **item))
        revision.issues = issues
        revision.extraction = extraction.regulatory_evidence(pages, revision.provenance)
        chunks = chunk_pages(pages)
        for chunk in chunks:
            index = chunk["chunk_index"]
            db.add(
                Chunk(
                    id=f"{document_id}_chunk_{index}",
                    document_id=document_id,
                    chunk_index=index,
                    content=chunk["content"],
                    provenance={
                        k: v for k, v in chunk.items() if k not in {"content", "chunk_index"}
                    },
                )
            )
        doc.chunk_count = len(chunks)
        db.commit()  # Extraction checkpoint: retries do not repeat OCR.
    owned(db, key, token)
    db.refresh(revision)
    if revision.issues and revision.review_status != "approved":
        revision.review_status = "required"
        doc.status = "review_required"
        doc.error_message = (
            "Extraction or document version needs review before it can be used in answers."
        )
        finish(db, key, token, state="review_required")
        return
    chunks = db.query(Chunk).filter_by(document_id=document_id).order_by(Chunk.chunk_index).all()
    if not chunks:
        raise ValueError("No usable text; upload a readable original and reprocess")
    payload = [{"content": c.content, "chunk_index": c.chunk_index} for c in chunks]
    metadata = {**revision.provenance, "created_at": doc.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    db.commit()  # Never hold database row locks over a remote call.
    from services.azure_search import index_document_chunks

    if not await index_document_chunks(document_id, doc.title, payload, metadata):
        raise RuntimeError("Azure Search indexing did not succeed; will retry")
    owned(db, key, token)
    source_lock(db, revision.source_key)
    newer = (
        db.query(Revision)
        .filter(
            Revision.source_key == revision.source_key,
            Revision.is_current.is_(True),
            Revision.created_at > revision.created_at,
        )
        .first()
    )
    if newer:
        doc.status = "superseded"
        finish(db, key, token, state="superseded")
        return
    # The current version changes only once indexing has succeeded.
    prior_ids = [
        r.id
        for r in db.query(Revision).filter_by(source_key=revision.source_key, is_current=True)
        if r.id != revision.id
    ]
    if prior_ids:
        db.query(Document).filter(Document.id.in_(prior_ids)).update(
            {"status": "superseded"}, synchronize_session="fetch"
        )
    db.query(Revision).filter_by(source_key=revision.source_key).update({"is_current": False})
    revision.is_current = True
    doc.status, doc.error_message = "indexed", None
    db.add(
        AuditLog(
            action="document_indexed",
            resource=f"documents/{document_id}",
            details={"sha256": revision.sha256, "chunks": len(chunks)},
        )
    )
    if revision.provenance.get("regulator") and not db.get(Alert, f"ingestion-{document_id}"):
        db.add(
            Alert(
                id=f"ingestion-{document_id}",
                title=f"Regulatory document ready: {doc.title}",
                summary="A preserved source is available for compliance review. Publication alone does not establish applicability.",
                severity="info",
                alert_type="regulatory_document",
                related_document_ids=[document_id],
                extra_metadata={"document_id": document_id, **revision.provenance},
            )
        )
    finish(db, key, token)


def reindex(db, document_id):
    """Rebuild search from saved chunks without discarding evidence or paying for OCR."""
    prepare_session(db)
    revision = db.get(Revision, document_id)
    doc = db.get(Document, document_id)
    if not revision or not revision.is_current or not doc:
        raise ValueError("Only a current published revision can be reindexed")
    enqueue(db, "document", document_id)
    doc.status = "pending"
    db.commit()


def review(db, document_id, user_id, decision, note):
    prepare_session(db)
    revision = db.query(Revision).filter_by(id=document_id).with_for_update().first()
    doc = db.get(Document, document_id)
    if not revision or not doc:
        raise ValueError("Document has no pipeline revision")
    if revision.review_status != "required":
        raise ValueError("Document is not awaiting review")
    if decision == "approve":
        if any("pending_ocr" in issue.get("reasons", []) for issue in revision.issues):
            raise ValueError("Incomplete OCR must be reprocessed before approval")
        if not db.query(Chunk).filter_by(document_id=document_id).count():
            raise ValueError("No text to approve; reprocess a readable original")
        revision.review_status = "approved"
        doc.status = "pending"
        enqueue(db, "document", document_id)
    elif decision == "reject":
        revision.review_status, doc.status = "rejected", "rejected"
    else:
        raise ValueError("Decision must be approve or reject")
    revision.reviewed_by, revision.reviewed_at, revision.review_note = (
        user_id,
        datetime.utcnow(),
        note,
    )
    db.add(
        AuditLog(
            user_id=user_id,
            action=f"document_{decision}",
            resource=f"documents/{document_id}",
            details={"note": note},
        )
    )
    db.commit()


def reprocess(db, document_id):
    prepare_session(db)
    revision = db.query(Revision).filter_by(id=document_id).with_for_update().first()
    doc = db.get(Document, document_id)
    if not revision or not doc:
        raise ValueError("Document has no preserved pipeline revision")
    job = db.get(Job, f"document:{document_id}")
    if job and job.state in {"queued", "retry", "running"}:
        raise ValueError("Document already has an active job")
    # Reprocessing a searchable revision would erase its citation checkpoints.
    if revision.is_current:
        raise ValueError("Upload a new version to replace an indexed document")
    db.query(Page).filter_by(document_id=document_id).delete()
    db.query(Chunk).filter_by(document_id=document_id).delete()
    revision.review_status, revision.issues, revision.extraction = "pending", [], {}
    revision.reviewed_by = revision.reviewed_at = revision.review_note = None
    doc.status, doc.error_message = "pending", None
    enqueue(db, "document", document_id)
    db.commit()
