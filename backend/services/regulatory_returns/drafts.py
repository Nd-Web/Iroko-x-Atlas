"""
services/regulatory_returns/drafts.py

The filing assistant: one saved draft per return and period, pre-filled by
Iroko and completed with the compliance officer.

    draft = open_draft(db, ws, user, "cbn-cg-compliance", "2026-H2")
    state(db, ws, draft)            # what Iroko filled, what it still needs
    answer(draft, {...})            # the officer's answers
    confirm(draft, [...])           # "looks right" on what Iroko filled
    await import_file(...)          # trial balance / loan book / transactions
    await find_in_documents(...)    # search the bank's documents for answers
    generate(db, ws, user, draft)   # the files, once nothing is outstanding

Every value records its source: memory, carried, document, derived, profile,
import or user. Nothing Iroko filled reaches a regulator until the officer has
confirmed it.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.filing import FilingDraft, FilingMemory, FilingProfile

from . import builders, importers
from .assist import datasets, hint
from .calendar import due_date, fy_end_month_for, parse_period
from .catalog import PROFILE_FIELDS, RETURNS_BY_ID, Field, ReturnSpec
from .evidence import find_answers, suggest_remediation
from .prudential import compute

CONFIRMABLE = {"memory", "carried", "document", "derived", "profile"}
# Table columns that describe one period only and so never carry forward.
PERIOD_COLUMNS = {"board": {"board_meetings_held", "board_meetings_attended"}, "committees": {"meetings_held"}}


def today() -> date:
    return datetime.now(builders.LAGOS).date()


# ─── Workspace, profile, memory ───────────────────────────────────────────────


def workspace_id(db: Session, user) -> str:
    from ingestion.access import ensure_workspace
    ws = ensure_workspace(db, user.id)
    db.commit()
    return ws


def get_profile(db: Session, ws: str) -> dict:
    row = db.get(FilingProfile, ws)
    return dict(row.profile) if row else {}


def profile_missing(profile: dict) -> list[str]:
    return [f.label for f in PROFILE_FIELDS if f.required and not str(profile.get(f.key) or "").strip()]


def save_profile(db: Session, ws: str, user, profile: dict) -> dict:
    allowed = {f.key for f in PROFILE_FIELDS}
    clean = {k: (str(v).strip() if v is not None else "") for k, v in (profile or {}).items() if k in allowed}
    row = db.get(FilingProfile, ws)
    if row is None:
        row = FilingProfile(workspace_id=ws, profile=clean, updated_by=user.id)
        db.add(row)
    else:
        row.profile = {**row.profile, **clean}
        row.updated_by = user.id
    db.commit()
    return dict(row.profile)


def memory(db: Session, ws: str, key: str, default: Any = None) -> Any:
    row = db.get(FilingMemory, (ws, key))
    return copy.deepcopy(row.value) if row else default


def remember(db: Session, ws: str, key: str, value: Any, note: str | None = None) -> None:
    row = db.get(FilingMemory, (ws, key))
    if row is None:
        db.add(FilingMemory(workspace_id=ws, key=key, value=value, note=note))
    else:
        row.value, row.note = value, note or row.note


# ─── Opening a draft ──────────────────────────────────────────────────────────


def _spec(return_id: str) -> ReturnSpec:
    spec = RETURNS_BY_ID.get(return_id)
    if spec is None or not spec.generator:
        raise HTTPException(404, "Unknown return, or one Iroko only tracks.")
    return spec


def _period_label(spec: ReturnSpec, period: str) -> str:
    if spec.period_type == "event":
        return "Event report"
    return parse_period(spec.period_type, period).label


def _filled(field: Field, value: Any) -> bool:
    if field.type == "table" or field.type == "multiselect":
        return isinstance(value, list) and any(
            isinstance(v, str) or any(x not in (None, "", False) for x in v.values()) for v in value
        )
    if field.type == "bool":
        return isinstance(value, bool)
    return value not in (None, "")


def open_draft(db: Session, ws: str, user, return_id: str, period: str | None) -> FilingDraft:
    spec = _spec(return_id)
    if spec.period_type == "event":
        period = f"event-{today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    else:
        try:
            period = parse_period(spec.period_type, period or "").key
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        existing = db.query(FilingDraft).filter_by(workspace_id=ws, return_id=return_id, period=period).first()
        if existing:
            return existing
    draft = FilingDraft(workspace_id=ws, return_id=return_id, period=period, data={}, sources={},
                        datasets={}, remediation={}, created_by=user.id)
    _prefill(db, ws, draft, spec)
    db.add(draft)
    db.commit()
    return draft


def _previous(db: Session, ws: str, draft: FilingDraft) -> FilingDraft | None:
    q = db.query(FilingDraft).filter(
        FilingDraft.workspace_id == ws, FilingDraft.return_id == draft.return_id, FilingDraft.period < draft.period
    )
    return q.order_by(FilingDraft.period.desc()).first()


def _set(draft: FilingDraft, key: str, value: Any, kind: str, label: str, **extra: Any) -> None:
    data, sources = dict(draft.data), dict(draft.sources)
    data[key] = value
    sources[key] = {"kind": kind, "label": label, "confirmed": kind not in CONFIRMABLE, **extra}
    draft.data, draft.sources = data, sources


def _prefill(db: Session, ws: str, draft: FilingDraft, spec: ReturnSpec) -> None:
    profile = get_profile(db, ws)
    prev = _previous(db, ws, draft)
    prev_label = _period_label(spec, prev.period) if prev else ""
    for f in spec.fields:
        h = hint(spec.id, f.key)
        if h.fact:
            value = memory(db, ws, f"fact:{h.fact}")
            if _filled(f, value):
                _set(draft, f.key, _strip_period_columns(f.key, value), "memory", "From your earlier filings")
                continue
        if h.carry and prev and _filled(f, prev.data.get(f.key)):
            _set(draft, f.key, _strip_period_columns(f.key, prev.data[f.key]), "carried", f"From your {prev_label} return")
            continue
        if h.default:
            value, label = _default(h.default, profile)
            if value not in (None, ""):
                _set(draft, f.key, value, "profile" if h.default == "cco_officer" else "derived", label)
    _derive_from_other_returns(db, ws, draft, spec)


def _strip_period_columns(key: str, value: Any) -> Any:
    cols = PERIOD_COLUMNS.get(key)
    if not cols or not isinstance(value, list):
        return copy.deepcopy(value)
    return [{k: ("" if k in cols else v) for k, v in row.items()} for row in value]


def _default(rule: str, profile: dict) -> tuple[Any, str]:
    if rule == "cco_officer":
        name = profile.get("cco_name")
        return (f"{name}, Chief Compliance Officer" if name else None), "Your Chief Compliance Officer"
    if rule == "today":
        return today().isoformat(), "Today"
    if rule.startswith("days_ago:"):
        n = int(rule.split(":")[1])
        return (today() - timedelta(days=n)).isoformat(), f"The last {n} days"
    return None, ""


def _december(db: Session, ws: str, year: int) -> FilingDraft | None:
    return db.query(FilingDraft).filter_by(workspace_id=ws, return_id="cbn-monthly-prudential", period=f"{year}-12").first()


def _derive_from_other_returns(db: Session, ws: str, draft: FilingDraft, spec: ReturnSpec) -> None:
    """Reuse figures the bank has already filed elsewhere."""
    if spec.id not in ("ndic-deposit-certification", "cbn-afs-submission"):
        return
    year = int(draft.period)
    dec = _december(db, ws, year)
    tb = (dec.datasets or {}).get("trial_balance") if dec else None
    if not tb or not tb.get("sfp"):
        return
    label = f"From your December {year} monthly return"
    sfp = tb["sfp"]
    if spec.id == "ndic-deposit-certification":
        for key, code in (("demand_deposits", "L01"), ("savings_deposits", "L02"), ("time_deposits", "L03"), ("other_deposits", "L04")):
            if key not in draft.data:
                _set(draft, key, round(sfp.get(code, 0.0), 2), "derived", label)
        return
    loans = importers.loans_from((dec.datasets or {}).get("loan_book") or {})
    totals = compute(sfp, tb["pl"], loans, get_profile(db, ws).get("licence_category", "")).totals
    note = label + " — replace with the audited figure if it differs"
    for key, value in (("total_assets", totals["total_assets"]), ("profit_before_tax", totals["profit_before_tax"]),
                       ("shareholders_funds", totals["shareholders_funds"])):
        if key not in draft.data:
            _set(draft, key, round(value, 2), "derived", note)


# ─── Questions and state ──────────────────────────────────────────────────────


def _applies(spec: ReturnSpec, data: dict, f: Field) -> bool:
    for key, expected in hint(spec.id, f.key).when:
        actual = data.get(key)
        if expected == "nonzero":
            try:
                if not actual or float(actual) == 0:
                    return False
            except (TypeError, ValueError):
                return False
        elif actual != expected:
            return False
    return True


def _zero_follow_up(spec: ReturnSpec, f: Field) -> bool:
    return f.type in ("number", "money") and any(e == "nonzero" for _, e in hint(spec.id, f.key).when)


def _zero_dependents(spec: ReturnSpec, draft: FilingDraft) -> None:
    """When nothing happened (0 reports received), the follow-up counts are 0 too."""
    for f in spec.fields:
        for key, expected in hint(spec.id, f.key).when:
            if expected != "nonzero" or f.type not in ("number", "money"):
                continue
            try:
                zero = draft.data.get(key) not in (None, "") and float(draft.data[key]) == 0
            except (TypeError, ValueError):
                zero = False
            if zero and draft.data.get(f.key) in (None, ""):
                _set(draft, f.key, 0, "user", "None, as nothing was reported")


def _question(spec: ReturnSpec, f: Field, period_label: str) -> dict:
    h = hint(spec.id, f.key)
    q = {
        "key": f.key, "label": f.label, "type": f.type, "required": f.required,
        "ask": (h.ask or f.label).replace("{period}", period_label.lower() if period_label.startswith("Half") else period_label),
        "help": f.help, "options": list(f.options),
        "columns": [asdict(c) for c in f.columns],
        "quick": [{"label": label, "value": value} for label, value in h.quick],
    }
    return q


def dataset_payload(draft: FilingDraft) -> dict:
    ds = draft.datasets or {}
    out: dict[str, Any] = {}
    tb = ds.get("trial_balance")
    if tb and tb.get("sfp"):
        out.update(sfp=tb["sfp"], pl=tb["pl"])
        out["loans"] = importers.loans_from(ds.get("loan_book") or {})
    tx = ds.get("transactions")
    if tx and tx.get("txns") is not None and not tx.get("needs_columns"):
        out["txns"] = importers.txns_from(tx)
    return out


def _dataset_state(kind: str, ds: dict | None, spec_ds) -> dict:
    base = {"kind": kind, "label": spec_ds.label, "ask": spec_ds.ask, "help": spec_ds.help, "required": spec_ds.required}
    if not ds:
        return {**base, "status": "missing"}
    common = {**base, "file_name": ds.get("file_name"), "headers": ds.get("headers", []),
              "columns": ds.get("columns", {}), "notes": ds.get("notes", []) + ds.get("warnings", [])}
    if ds.get("needs_columns"):
        return {**common, "status": "needs_columns", "needs_columns": ds["needs_columns"]}
    if kind == "trial_balance":
        accounts = ds.get("accounts", [])
        unmapped = sum(1 for a in accounts if not a.get("line"))
        ai = sum(1 for a in accounts if a.get("how", "").startswith("Iroko AI"))
        status = "ready" if ds.get("confirmed") and not unmapped else "needs_review"
        return {**common, "status": status, "accounts": accounts, "unmapped": unmapped, "ai_mapped": ai,
                "notes": ds.get("notes", []) + ds.get("warnings", [])}
    if kind == "loan_book":
        loans = ds.get("loans", [])
        review = sorted(loans, key=lambda l: l["outstanding"], reverse=True)[:25]
        review_rows = {l["row"] for l in review}
        review += [l for l in loans if (l["insider"] or l["borrower_type"] != "Individual") and l["row"] not in review_rows][:75]
        return {**common, "status": "ready" if ds.get("confirmed") else "needs_review", "count": len(loans),
                "total": round(sum(l["outstanding"] for l in loans), 2), "review": review}
    txns = ds.get("txns", [])
    return {**common, "status": "ready", "count": len(txns)}


def state(db: Session, ws: str, draft: FilingDraft) -> dict:
    spec = _spec(draft.return_id)
    profile = get_profile(db, ws)
    label = _period_label(spec, draft.period)
    _zero_dependents(spec, draft)
    questions, items, optional = [], [], []
    for f in spec.fields:
        if not _applies(spec, draft.data, f):
            continue
        value = draft.data.get(f.key)
        src = draft.sources.get(f.key)
        if src and (_filled(f, value) or f.type == "bool"):
            items.append({"key": f.key, "label": f.label, "type": f.type, "value": value, "source": src,
                          "options": list(f.options), "columns": [asdict(c) for c in f.columns]})
        elif f.required or hint(spec.id, f.key).ask:
            questions.append(_question(spec, f, label))
        else:
            optional.append(_question(spec, f, label))
    ds_state = [_dataset_state(d.kind, (draft.datasets or {}).get(d.kind), d) for d in datasets(spec.id)]
    unconfirmed = [i["key"] for i in items if not i["source"].get("confirmed")]
    datasets_ready = all(d["status"] == "ready" for d in ds_state if d["required"])
    missing_profile = profile_missing(profile)
    total = len(questions) + len(items) + len(ds_state)
    done = len(items) - len(unconfirmed) + sum(1 for d in ds_state if d["status"] == "ready")
    check = None
    if not questions and datasets_ready and not missing_profile:
        check = builders.preview(_prepared(draft, profile))
    period = None if spec.period_type == "event" else parse_period(spec.period_type, draft.period, fy_end_month_for(spec, 12))
    due = due_date(spec, period) if period else None
    if spec.period_type == "event":
        # STR: 24 hours from detection. CTR: 7 days from the earliest transaction in the batch.
        start = builders._parse_date(draft.data.get("period_from") if spec.id == "nfiu-ctr" else draft.data.get("detection_datetime"))
        if start:
            due = start + timedelta(days=7 if spec.id == "nfiu-ctr" else 1)
    blocking = []
    if missing_profile:
        blocking.append("Complete the bank details: " + ", ".join(missing_profile) + ".")
    if questions:
        blocking.append(f"Answer {len(questions)} question{'s' if len(questions) != 1 else ''}.")
    if not datasets_ready:
        blocking.append("Finish the data imports.")
    if unconfirmed:
        blocking.append(f"Confirm {len(unconfirmed)} answer{'s' if len(unconfirmed) != 1 else ''} Iroko filled in.")
    if check and check["errors"]:
        blocking.append("Fix the problems found in the check.")
    if check and check["remediation_required"]:
        blocking.append("Add a remediation plan for each exception.")
    return {
        "draft": {
            "id": draft.id, "return_id": draft.return_id, "period": draft.period, "period_label": label,
            "status": draft.status, "reference": draft.reference, "submission_ref": draft.submission_ref,
            "submitted_on": draft.submitted_on, "letter_date": draft.letter_date or today().isoformat(),
            "due": due.isoformat() if due else None, "days_left": (due - today()).days if due else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        },
        "progress": {"done": done, "total": total},
        "profile": profile, "profile_missing": missing_profile,
        "questions": questions, "items": items, "optional": optional, "unconfirmed": unconfirmed,
        "datasets": ds_state, "remediation": draft.remediation or {},
        "check": check, "blocking": blocking, "ready": not blocking,
        "can_search_documents": any(hint(spec.id, f.key).evidence for f in spec.fields),
    }


def _prepared(draft: FilingDraft, profile: dict) -> builders.Prepared:
    spec = _spec(draft.return_id)
    payload = {
        "profile": profile,
        "period": None if spec.period_type == "event" else draft.period,
        "letter_date": draft.letter_date or today().isoformat(),
        # Fields switched off by an earlier answer are left out (no fraud → no case list), except
        # counts that follow from "nothing happened", which are filled with 0.
        "data": {k: v for k, v in draft.data.items()
                 if any(f.key == k and (_applies(spec, draft.data, f) or _zero_follow_up(spec, f)) for f in spec.fields)},
        "remediation": draft.remediation or {},
    }
    if spec.period_type == "event" and draft.reference:
        payload["reference"] = draft.reference
    return builders.prepare(draft.return_id, payload, dataset=dataset_payload(draft))


# ─── Changes ──────────────────────────────────────────────────────────────────


def answer(draft: FilingDraft, values: dict) -> None:
    spec = _spec(draft.return_id)
    keys = {f.key for f in spec.fields}
    for key, value in (values or {}).items():
        if key in keys:
            _set(draft, key, value, "user", "Entered by you")
    if draft.status != "submitted":
        draft.status = "draft"


def clear(draft: FilingDraft, keys: list[str]) -> None:
    data, sources = dict(draft.data), dict(draft.sources)
    for k in keys:
        data.pop(k, None)
        sources.pop(k, None)
    draft.data, draft.sources = data, sources


def confirm(draft: FilingDraft, keys: list[str]) -> None:
    sources = copy.deepcopy(draft.sources)
    for k in keys:
        if k in sources:
            sources[k]["confirmed"] = True
    draft.sources = sources


def set_remediation(draft: FilingDraft, remediation: dict) -> None:
    draft.remediation = {**(draft.remediation or {}), **{str(k): str(v) for k, v in remediation.items()}}


def _gl_memory(db: Session, ws: str) -> dict[str, str]:
    return memory(db, ws, "gl_mapping", {}) or {}


def _board_names(db: Session, ws: str) -> list[str]:
    board = memory(db, ws, "fact:board", []) or []
    names = [row.get("name", "") for row in board if isinstance(row, dict)]
    profile = get_profile(db, ws)
    return [n for n in names + [profile.get("md_ceo_name", "")] if n]


async def import_file(db: Session, ws: str, draft: FilingDraft, kind: str, data: bytes, filename: str, complete) -> None:
    spec = _spec(draft.return_id)
    if kind not in {d.kind for d in datasets(spec.id)}:
        raise HTTPException(400, f"{spec.short_title} does not take a {kind.replace('_', ' ')} file.")
    try:
        if kind == "trial_balance":
            result = await importers.import_trial_balance(data, filename, _gl_memory(db, ws), complete)
        elif kind == "loan_book":
            result = await importers.import_loan_book(data, filename, _board_names(db, ws), complete)
        else:
            result = await importers.import_transactions(data, filename, complete)
    except importers.TemplateError as exc:
        raise HTTPException(422, " ".join(exc.problems)) from None
    draft.datasets = {**(draft.datasets or {}), kind: result}
    draft.status = "draft"


async def set_columns(db: Session, ws: str, draft: FilingDraft, kind: str, columns: dict[str, int], complete) -> None:
    ds = (draft.datasets or {}).get(kind)
    if not ds:
        raise HTTPException(404, "Upload the file first.")
    cols = {**ds.get("columns", {}), **{k: int(v) for k, v in columns.items() if v is not None and int(v) >= 0}}
    if kind == "trial_balance":
        result = await importers.rebuild_tb(ds, cols, _gl_memory(db, ws), complete)
    elif kind == "loan_book":
        result = await importers.build_loan_book(ds["file_name"], ds["headers"], ds["rows"], _board_names(db, ws), complete, cols)
    else:
        result = await importers.build_transactions(ds["file_name"], ds["headers"], ds["rows"], complete, cols)
    draft.datasets = {**draft.datasets, kind: result}


def review_dataset(db: Session, ws: str, draft: FilingDraft, kind: str, changes: dict, confirm_all: bool) -> None:
    ds = copy.deepcopy((draft.datasets or {}).get(kind))
    if not ds:
        raise HTTPException(404, "Upload the file first.")
    if kind == "trial_balance":
        if changes.get("lines"):
            importers.remap_tb(ds, changes["lines"])
        if confirm_all:
            if any(not a.get("line") for a in ds["accounts"]):
                raise HTTPException(409, "Choose a line (or 'Not reported') for every unmapped account first.")
            for a in ds["accounts"]:
                if a.get("how", "").startswith("Iroko AI"):
                    a["how"] = "Confirmed by you"
            ds["confirmed"] = True
            mapping = _gl_memory(db, ws)
            mapping.update({a["code"]: a["line"] for a in ds["accounts"] if a.get("line")})
            remember(db, ws, "gl_mapping", mapping, "GL account → MMFBR line, learned from confirmed trial balances")
    elif kind == "loan_book":
        by_row = {str(l["row"]): l for l in ds.get("loans", [])}
        for row, change in (changes.get("loans") or {}).items():
            loan = by_row.get(str(row))
            if not loan:
                continue
            if change.get("borrower_type") in ("Individual", "Group", "Cooperative", "Corporate"):
                loan["borrower_type"] = change["borrower_type"]
            if "insider" in change:
                loan["insider"] = bool(change["insider"])
                if loan["insider"] and not loan.get("insider_relationship"):
                    loan["insider_relationship"] = change.get("insider_relationship") or "Insider (marked by you)"
        if confirm_all:
            ds["confirmed"] = True
    draft.datasets = {**draft.datasets, kind: ds}


async def find_in_documents(db: Session, ws: str, draft: FilingDraft, retrieve, complete) -> int:
    spec = _spec(draft.return_id)
    profile = get_profile(db, ws)
    empty = [f for f in spec.fields if not _filled(f, draft.data.get(f.key)) and _applies(spec, draft.data, f)]
    found = await find_answers(spec.id, empty, _period_label(spec, draft.period), profile.get("institution_name", ""), retrieve, complete)
    for key, a in found.items():
        _set(draft, key, a["value"], "document", f"Found in “{a['title']}”", quote=a["quote"], document_id=a["document_id"])
    return len(found)


async def remediation_suggestion(db: Session, ws: str, draft: FilingDraft, code: str, complete) -> str:
    prepared = _prepared(draft, get_profile(db, ws))
    breaches = [b for b in prepared.breaches if b["code"] == code]
    if not breaches:
        raise HTTPException(404, "That exception is no longer present.")
    title = breaches[0].get("group") or breaches[0]["title"]
    detail = " ".join(b["detail"] for b in breaches)
    return await suggest_remediation(title, detail, prepared.profile.get("institution_name", ""), prepared.letter_date.isoformat(), complete)


# ─── Generate and submit ──────────────────────────────────────────────────────


def generate(db: Session, ws: str, draft: FilingDraft) -> tuple[builders.Prepared, list[tuple[str, bytes, str]]]:
    current = state(db, ws, draft)
    if not current["ready"]:
        raise builders.ReturnInputError(current["blocking"])
    prepared = _prepared(draft, current["profile"])
    files = builders.render(prepared)
    spec = _spec(draft.return_id)
    for f in spec.fields:  # facts the next filing can start from
        h = hint(spec.id, f.key)
        if h.fact and _filled(f, draft.data.get(f.key)):
            remember(db, ws, f"fact:{h.fact}", draft.data[f.key])
    draft.reference = prepared.reference
    if draft.status != "submitted":
        draft.status = "generated"
    draft.generated_at = datetime.utcnow()
    return prepared, files


def mark_submitted(draft: FilingDraft, user, submission_ref: str, submitted_on: str | None) -> None:
    if draft.status not in ("generated", "submitted"):
        raise HTTPException(409, "Generate the documents before marking the return as submitted.")
    draft.status = "submitted"
    draft.submission_ref = (submission_ref or "").strip()[:200]
    draft.submitted_on = submitted_on or today().isoformat()
    draft.submitted_by = user.id


def statuses(db: Session, ws: str) -> dict[tuple[str, str], dict]:
    rows = db.query(FilingDraft).filter_by(workspace_id=ws).all()
    return {(r.return_id, r.period): {"status": r.status, "draft_id": r.id, "submitted_on": r.submitted_on} for r in rows}


def list_events(db: Session, ws: str, return_id: str) -> list[dict]:
    rows = (db.query(FilingDraft).filter_by(workspace_id=ws, return_id=return_id)
            .order_by(FilingDraft.created_at.desc()).limit(50).all())
    return [{"id": r.id, "period": r.period, "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None,
             "subject": r.data.get("subject_name") or r.data.get("period_from") or "", "reference": r.reference} for r in rows]
