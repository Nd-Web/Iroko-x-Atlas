"""
schedulers/index_scheduler.py — Document re-indexing scheduler for Iroko AI.

Runs every 30 minutes via APScheduler's ``AsyncIOScheduler``.  On each tick:

1. Queries the database for documents with status "pending" or "failed".
2. Re-attempts Azure AI Search indexing for each document.
3. Updates document status to "indexed" on success or "failed" on error.
4. Logs results.

Start via ``start_index_scheduler()`` in the FastAPI lifespan handler.
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# ── Scheduler singleton ───────────────────────────────────────────────────────

_scheduler: Optional[AsyncIOScheduler] = None


def _get_scheduler() -> AsyncIOScheduler:
    """Return the singleton AsyncIOScheduler, creating it if needed."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


# ── Index job ─────────────────────────────────────────────────────────────────

async def _index_pending_documents():
    """
    Find all documents with status "pending" or "failed" and re-attempt
    indexing via the document processor pipeline.
    """
    from models.database import SessionLocal, Document

    db = SessionLocal()
    try:
        pending_docs = (
            db.query(Document)
            .filter(Document.status.in_(["pending", "failed"]))
            .all()
        )

        if not pending_docs:
            logger.debug("Index scheduler: no pending/failed documents to process.")
            return

        logger.info(
            f"Index scheduler: found {len(pending_docs)} document(s) to process."
        )

        indexed = 0
        failed = 0

        for doc in pending_docs:
            try:
                doc.status = "processing"
                db.commit()

                # Attempt to process and index the document
                from services.document_processor import process_document

                # Determine file path — use blob download if local file doesn't exist
                import os
                local_path = None

                if doc.blob_url:
                    # Download from blob storage to a temp path
                    from services.blob_storage import download_document
                    tmp_dir = os.path.join(
                        os.path.dirname(__file__), "..", "tmp_index_downloads"
                    )
                    os.makedirs(tmp_dir, exist_ok=True)
                    local_path = os.path.join(
                        tmp_dir, f"{doc.id}.{doc.file_type}"
                    )
                    try:
                        await download_document(doc.blob_url, local_path)
                    except Exception as dl_err:
                        logger.warning(
                            f"Could not download blob for doc {doc.id}: {dl_err}"
                        )
                        doc.status = "failed"
                        doc.error_message = f"Blob download failed: {dl_err}"
                        db.commit()
                        failed += 1
                        continue

                if not local_path or not os.path.exists(local_path):
                    doc.status = "failed"
                    doc.error_message = "Source file not available for re-indexing."
                    db.commit()
                    failed += 1
                    continue

                result = await process_document(
                    file_path=local_path,
                    document_id=doc.id,
                    title=doc.title,
                    metadata={
                        "department": doc.department or "",
                        "doc_type": doc.file_type,
                        "file_type": doc.file_type,
                        "filename": doc.filename,
                        "blob_url": doc.blob_url or "",
                        "classification": "internal",
                        "language": "en",
                        "region": "",
                    },
                )

                if result.get("success"):
                    doc.status = "indexed"
                    doc.chunk_count = result.get("chunk_count", 0)
                    doc.error_message = None
                    doc.updated_at = datetime.utcnow()
                    indexed += 1
                    logger.info(
                        f"Index scheduler: doc '{doc.title}' ({doc.id}) "
                        f"indexed — {doc.chunk_count} chunks."
                    )
                else:
                    doc.status = "failed"
                    doc.error_message = result.get("error", "Unknown processing error")
                    failed += 1
                    logger.warning(
                        f"Index scheduler: doc '{doc.title}' ({doc.id}) "
                        f"failed — {doc.error_message}"
                    )

                db.commit()

                # Clean up temp file
                try:
                    if local_path and os.path.exists(local_path):
                        os.remove(local_path)
                except Exception:
                    pass

            except Exception as exc:
                logger.error(
                    f"Index scheduler: unexpected error for doc {doc.id}: {exc}",
                    exc_info=True,
                )
                doc.status = "failed"
                doc.error_message = f"Unexpected error: {str(exc)[:200]}"
                db.commit()
                failed += 1

        logger.info(
            f"Index scheduler complete: {indexed} indexed, {failed} failed, "
            f"{len(pending_docs)} total processed."
        )

    except Exception as exc:
        logger.error(f"Index scheduler tick failed: {exc}", exc_info=True)
    finally:
        db.close()


# ── Public API ────────────────────────────────────────────────────────────────

def start_index_scheduler():
    """
    Start the index scheduler.  Call this once during FastAPI lifespan startup.

    Adds a job that runs ``_index_pending_documents`` every 30 minutes.
    """
    scheduler = _get_scheduler()

    if scheduler.running:
        logger.debug("Index scheduler already running — skipping start.")
        return

    scheduler.add_job(
        _index_pending_documents,
        IntervalTrigger(minutes=30),
        id="index_pending_docs",
        replace_existing=True,
        max_instances=1,
        name="Re-index pending/failed documents",
    )
    scheduler.start()
    logger.info("Index scheduler started (30-minute interval).")


def stop_index_scheduler():
    """Gracefully shut down the index scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Index scheduler stopped.")
    _scheduler = None
