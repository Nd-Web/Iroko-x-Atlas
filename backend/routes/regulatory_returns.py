"""
routes/regulatory_returns.py

Regulatory returns for microfinance banks (CBN · NFIU · NDIC · NDPC).

  GET  /api/returns/catalog               returns, profile schema, upcoming deadlines
  GET  /api/returns/{id}/template         Excel input template (upload-based returns)
  POST /api/returns/{id}/preview          validate + compute → errors, warnings, breaches, figures
  POST /api/returns/{id}/generate         render → .docx, or a .zip when there are several files

Preview and generate take multipart form data: `payload` (JSON string with
profile, period, data, remediation, optional letter_date/reference) and an
optional `file` (.xlsx). Nothing is stored except an audit-log entry of each
generation.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from models.database import AuditLog, User, get_db
from services.auth_utils import get_current_user
from services.regulatory_returns import builders, calendar, catalog, templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/returns", tags=["Regulatory returns"])


def _spec(return_id: str) -> catalog.ReturnSpec:
    spec = catalog.RETURNS_BY_ID.get(return_id)
    if spec is None:
        raise HTTPException(404, f"Unknown return '{return_id}'.")
    return spec


async def _read_inputs(payload: str, file: UploadFile | None) -> tuple[dict, bytes | None]:
    try:
        data = json.loads(payload or "{}")
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(400, "payload must be a JSON object.") from None
    upload = None
    if file is not None and file.filename:
        upload = await file.read(templates.MAX_UPLOAD_BYTES + 1)
        if len(upload) > templates.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "The uploaded file exceeds the 10 MB limit.")
    return data, upload


@router.get("/catalog")
async def get_catalog(
    fy_end_month: int = Query(12, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    today = datetime.now(builders.LAGOS).date()
    return {
        "returns": catalog.catalog_dict(),
        "profile_fields": catalog.profile_schema(),
        "licence_categories": catalog.LICENCE_CATEGORIES,
        "calendar": calendar.upcoming(today, per_return=2, fy_end_month=fy_end_month),
        "today": today.isoformat(),
        "holiday_note": "Deadlines move to the previous working day for weekends, fixed public holidays and Easter. "
                        "Islamic holidays are declared annually — check FinA deadlines against the Federal Government's announcements.",
    }


@router.get("/{return_id}/template")
async def get_template(return_id: str, current_user: User = Depends(get_current_user)):
    spec = _spec(return_id)
    if not spec.upload:
        raise HTTPException(404, "This return is completed in the form; it has no upload template.")
    content = await run_in_threadpool(templates.TEMPLATES[spec.upload])
    return Response(
        content,
        media_type=builders.XLSX,
        headers={"Content-Disposition": f'attachment; filename="iroko-{spec.id}-input.xlsx"', "Cache-Control": "no-store"},
    )


@router.post("/{return_id}/preview")
async def preview_return(
    return_id: str,
    payload: str = Form("{}"),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
):
    spec = _spec(return_id)
    if not spec.generator:
        raise HTTPException(400, f"{spec.short_title} is prepared outside Iroko; only its deadline is tracked.")
    data, upload = await _read_inputs(payload, file)
    prepared = await run_in_threadpool(builders.prepare, return_id, data, upload)
    return builders.preview(prepared)


@router.post("/{return_id}/generate")
async def generate_return(
    return_id: str,
    payload: str = Form("{}"),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    spec = _spec(return_id)
    if not spec.generator:
        raise HTTPException(400, f"{spec.short_title} is prepared outside Iroko; only its deadline is tracked.")
    data, upload = await _read_inputs(payload, file)
    prepared = await run_in_threadpool(builders.prepare, return_id, data, upload)
    try:
        files = await run_in_threadpool(builders.render, prepared)
    except builders.ReturnInputError as exc:
        return JSONResponse({"detail": "The return is not ready to generate.", "errors": exc.errors}, status_code=422)

    try:
        db.add(AuditLog(
            user_id=current_user.id,
            action="regulatory_return_generated",
            resource=f"returns/{spec.id}",
            details={
                "reference": prepared.reference,
                "period": prepared.period.key if prepared.period else None,
                "institution": prepared.profile.get("institution_name"),
                "breaches": len(prepared.breaches),
                "files": [name for name, _, _ in files],
            },
        ))
        db.commit()
    except Exception:  # audit logging must never block a filing
        db.rollback()
        logger.exception("[returns] audit log write failed for %s", spec.id)

    if len(files) == 1:
        name, content, media = files[0]
        return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content, _ in files:
            zf.writestr(name, content)
    zip_name = prepared.reference.replace("/", "_") + ".zip"
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{zip_name}"', "Cache-Control": "no-store"})
