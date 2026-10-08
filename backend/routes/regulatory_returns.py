"""
routes/regulatory_returns.py

Regulatory returns for microfinance banks (CBN · NFIU · NDIC · NDPC).

Filing assistant (saved per workspace):
  GET   /api/returns/catalog                      returns, deadlines with each filing's status
  GET   /api/returns/profile                      the bank's particulars (shared by the team)
  PUT   /api/returns/profile
  POST  /api/returns/drafts                       open (or resume) a return for a period
  GET   /api/returns/drafts/{id}                  what Iroko filled, what it still needs
  PATCH /api/returns/drafts/{id}                  answers, confirmations, remediation, letter date
  POST  /api/returns/drafts/{id}/import/{kind}    trial balance / loan book / transactions (any layout)
  POST  /api/returns/drafts/{id}/columns/{kind}   choose columns Iroko could not find
  POST  /api/returns/drafts/{id}/review/{kind}    correct and confirm an import
  POST  /api/returns/drafts/{id}/find             search the bank's documents for answers
  POST  /api/returns/drafts/{id}/suggest          draft a remediation plan for one exception
  POST  /api/returns/drafts/{id}/generate         the documents (.docx, or .zip of several)
  POST  /api/returns/drafts/{id}/submitted        record the FinA / goAML submission
  GET   /api/returns/events/{return_id}           STR / CTR drafts

Stateless (inputs in the request, nothing stored but an audit entry):
  GET  /api/returns/{id}/template   ·   POST /api/returns/{id}/preview   ·   POST /api/returns/{id}/generate
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from models.database import AuditLog, User, get_db
from models.filing import FilingDraft
from services.auth_utils import get_current_user
from services.regulatory_returns import assist, builders, calendar, catalog, drafts, templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/returns", tags=["Regulatory returns"])


async def _complete(prompt: str, **kwargs) -> str:
    from agents.kernel import llm_complete
    return await llm_complete(prompt, **kwargs)


async def _retrieve(question: str) -> dict:
    from services.grounded_answers import retrieve
    return await retrieve(question)


def _spec(return_id: str) -> catalog.ReturnSpec:
    spec = catalog.RETURNS_BY_ID.get(return_id)
    if spec is None:
        raise HTTPException(404, f"Unknown return '{return_id}'.")
    return spec


def _audit(db: Session, user: User, action: str, resource: str, details: dict) -> None:
    try:
        db.add(AuditLog(user_id=user.id, action=action, resource=resource, details=details))
        db.commit()
    except Exception:  # audit logging must never block a filing
        db.rollback()
        logger.exception("[returns] audit log write failed for %s", resource)


def _files_response(files: list[tuple[str, bytes, str]], reference: str) -> Response:
    headers = {"Cache-Control": "no-store"}
    if len(files) == 1:
        name, content, media = files[0]
        return Response(content, media_type=media, headers={**headers, "Content-Disposition": f'attachment; filename="{name}"'})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content, _ in files:
            zf.writestr(name, content)
    zip_name = reference.replace("/", "_") + ".zip"
    return Response(buf.getvalue(), media_type="application/zip", headers={**headers, "Content-Disposition": f'attachment; filename="{zip_name}"'})


async def _read_upload(file: UploadFile | None) -> bytes | None:
    if file is None or not file.filename:
        return None
    data = await file.read(templates.MAX_UPLOAD_BYTES + 1)
    if len(data) > templates.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The uploaded file exceeds the 10 MB limit.")
    return data


# ─── Catalogue ────────────────────────────────────────────────────────────────


@router.get("/catalog")
async def get_catalog(
    fy_end_month: int = Query(12, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(builders.LAGOS).date()
    ws = drafts.workspace_id(db, current_user)
    status = drafts.statuses(db, ws)
    items = calendar.upcoming(today, per_return=2, fy_end_month=fy_end_month)
    for item in items:
        item.update(status.get((item["return_id"], item["period"]), {"status": "not_started", "draft_id": None}))
    returns = catalog.catalog_dict()
    for r in returns:
        r["datasets"] = assist.datasets_dict(r["id"])
    return {
        "returns": returns,
        "profile_fields": catalog.profile_schema(),
        "licence_categories": catalog.LICENCE_CATEGORIES,
        "calendar": items,
        "profile_missing": drafts.profile_missing(drafts.get_profile(db, ws)),
        "today": today.isoformat(),
        "holiday_note": "Deadlines move to the previous working day for weekends, fixed public holidays and Easter. "
                        "Islamic holidays are declared annually — check FinA deadlines against the Federal Government's announcements.",
    }


# ─── Filing assistant ─────────────────────────────────────────────────────────


@router.get("/profile")
async def read_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    profile = drafts.get_profile(db, ws)
    return {"profile": profile, "missing": drafts.profile_missing(profile)}


@router.put("/profile")
async def write_profile(profile: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    saved = drafts.save_profile(db, ws, current_user, profile)
    return {"profile": saved, "missing": drafts.profile_missing(saved)}


def _draft(db: Session, ws: str, draft_id: str) -> FilingDraft:
    draft = db.query(FilingDraft).filter_by(id=draft_id, workspace_id=ws).first()
    if draft is None:
        raise HTTPException(404, "Draft not found.")
    return draft


def _state(db: Session, ws: str, draft: FilingDraft) -> dict:
    result = drafts.state(db, ws, draft)
    db.commit()
    return result


@router.post("/drafts")
async def open_draft(body: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = drafts.open_draft(db, ws, current_user, str(body.get("return_id") or ""), body.get("period"))
    return await run_in_threadpool(_state, db, ws, draft)


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    return await run_in_threadpool(_state, db, ws, _draft(db, ws, draft_id))


@router.patch("/drafts/{draft_id}")
async def update_draft(draft_id: str, body: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    if body.get("answers"):
        drafts.answer(draft, body["answers"])
    if body.get("clear"):
        drafts.clear(draft, list(body["clear"]))
    if body.get("confirm"):
        drafts.confirm(draft, list(body["confirm"]))
    if body.get("remediation"):
        drafts.set_remediation(draft, body["remediation"])
    if body.get("letter_date"):
        draft.letter_date = str(body["letter_date"])[:10]
    db.commit()
    return await run_in_threadpool(_state, db, ws, draft)


@router.post("/drafts/{draft_id}/import/{kind}")
async def import_data(draft_id: str, kind: str, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    data = await _read_upload(file)
    if not data:
        raise HTTPException(400, "Choose a file to upload.")
    await drafts.import_file(db, ws, draft, kind, data, file.filename or "upload.xlsx", _complete)
    db.commit()
    return await run_in_threadpool(_state, db, ws, draft)


@router.post("/drafts/{draft_id}/columns/{kind}")
async def choose_columns(draft_id: str, kind: str, body: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    await drafts.set_columns(db, ws, draft, kind, body.get("columns") or {}, _complete)
    db.commit()
    return await run_in_threadpool(_state, db, ws, draft)


@router.post("/drafts/{draft_id}/review/{kind}")
async def review_import(draft_id: str, kind: str, body: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    drafts.review_dataset(db, ws, draft, kind, body.get("changes") or {}, bool(body.get("confirm")))
    db.commit()
    return await run_in_threadpool(_state, db, ws, draft)


@router.post("/drafts/{draft_id}/find")
async def find_answers(draft_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    found = await drafts.find_in_documents(db, ws, draft, _retrieve, _complete)
    db.commit()
    result = await run_in_threadpool(_state, db, ws, draft)
    return {**result, "found": found}


@router.post("/drafts/{draft_id}/suggest")
async def suggest(draft_id: str, body: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    try:
        text = await drafts.remediation_suggestion(db, ws, draft, str(body.get("code") or ""), _complete)
    except RuntimeError:
        raise HTTPException(503, "Iroko could not draft a suggestion right now — write the plan yourself or try again.") from None
    if not text:
        raise HTTPException(503, "Iroko could not draft a suggestion right now — write the plan yourself or try again.")
    return {"code": body.get("code"), "suggestion": text}


@router.post("/drafts/{draft_id}/generate")
async def generate_draft(draft_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    try:
        prepared, files = await run_in_threadpool(drafts.generate, db, ws, draft)
    except builders.ReturnInputError as exc:
        return JSONResponse({"detail": "The return is not ready to generate.", "errors": exc.errors}, status_code=422)
    db.commit()
    _audit(db, current_user, "regulatory_return_generated", f"returns/{draft.return_id}", {
        "draft_id": draft.id, "reference": prepared.reference, "period": draft.period,
        "institution": prepared.profile.get("institution_name"), "breaches": len(prepared.breaches),
        "files": [name for name, _, _ in files],
    })
    return _files_response(files, prepared.reference)


@router.post("/drafts/{draft_id}/submitted")
async def submitted(draft_id: str, body: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    draft = _draft(db, ws, draft_id)
    drafts.mark_submitted(draft, current_user, str(body.get("submission_ref") or ""), body.get("submitted_on"))
    db.commit()
    _audit(db, current_user, "regulatory_return_submitted", f"returns/{draft.return_id}", {
        "draft_id": draft.id, "reference": draft.reference, "period": draft.period,
        "submission_ref": draft.submission_ref, "submitted_on": draft.submitted_on,
    })
    return await run_in_threadpool(_state, db, ws, draft)


@router.get("/events/{return_id}")
async def events(return_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = drafts.workspace_id(db, current_user)
    return {"drafts": drafts.list_events(db, ws, return_id)}


# ─── Stateless generation ─────────────────────────────────────────────────────


async def _read_inputs(payload: str, file: UploadFile | None) -> tuple[dict, bytes | None]:
    try:
        data = json.loads(payload or "{}")
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(400, "payload must be a JSON object.") from None
    return data, await _read_upload(file)


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
    _audit(db, current_user, "regulatory_return_generated", f"returns/{spec.id}", {
        "reference": prepared.reference, "period": prepared.period.key if prepared.period else None,
        "institution": prepared.profile.get("institution_name"), "breaches": len(prepared.breaches),
        "files": [name for name, _, _ in files],
    })
    return _files_response(files, prepared.reference)
