"""Transactional workspace quotas, shared across API replicas and workers."""

import os
from datetime import datetime

from ingestion.db import source_lock
from ingestion.models import DocumentAccess, Job, WorkspaceUsage
from ingestion.validation import UploadLimitError


def usage(db, workspace):
    key = f"{datetime.utcnow().date().isoformat()}:{workspace}"
    source_lock(db, f"usage:{key}")
    row = db.get(WorkspaceUsage, key, populate_existing=True)
    if row is None:
        row = WorkspaceUsage(key=key, uploads=0, bytes=0, ocr_pages=0)
        db.add(row)
    return row


def reserve_upload(db, workspace, size):
    row = usage(db, workspace)
    if row.uploads >= int(os.getenv("WORKSPACE_DAILY_UPLOAD_LIMIT", "50")):
        raise UploadLimitError("Workspace daily upload limit reached")
    if row.bytes + size > int(os.getenv("WORKSPACE_DAILY_UPLOAD_BYTES", str(250 * 1024 * 1024))):
        raise UploadLimitError("Workspace daily upload size limit reached")
    pending = (
        db.query(Job)
        .join(DocumentAccess, DocumentAccess.document_id == Job.target_id)
        .filter(
            DocumentAccess.workspace_id == workspace,
            Job.kind == "document",
            Job.state.in_(["queued", "retry", "running"]),
        )
        .count()
    )
    if pending >= int(os.getenv("WORKSPACE_PENDING_DOCUMENT_LIMIT", "25")):
        raise UploadLimitError("Workspace processing queue is full; wait for existing uploads")
    row.uploads += 1
    row.bytes += size


def reserve_workspace_ocr(db, workspace, requested):
    row = usage(db, workspace)
    allowed = min(
        requested, max(0, int(os.getenv("WORKSPACE_DAILY_OCR_PAGES", "200")) - row.ocr_pages)
    )
    row.ocr_pages += allowed
    return allowed
