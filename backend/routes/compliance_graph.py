"""
Compliance knowledge graph API: /api/compliance-graph/*

Reads only the database (no model or web calls), always through the caller's
workspace scope. Review decisions follow the split agreed for the pilot:
the Iroko team (superadmins) confirms shared regulation facts; a workspace's
admins confirm their own controls, evidence and decisions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ingestion.db import prepare_session
from models.database import AuditLog, User, get_db
from services.auth_utils import get_current_user
from services.compliance_graph import common, queries, review, taxonomy
from services.compliance_graph.permissions import GraphError
from services.compliance_graph.visibility import for_user

router = APIRouter(prefix="/api/compliance-graph", tags=["Compliance graph"])


def _enabled():
    if not common.enabled():
        raise HTTPException(503, "The compliance graph is not enabled yet")


def scoped(user: User = Depends(get_current_user), db=Depends(get_db)) -> tuple:
    _enabled()
    prepare_session(db)
    return for_user(db, user), user


def run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except GraphError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


# ─── Request bodies ──────────────────────────────────────────────────────────


class ReviewBody(BaseModel):
    kind: Literal["link", "requirement", "control"] = "link"
    id: str = Field(min_length=1, max_length=100)
    decision: Literal["confirm", "reject", "reopen"]
    note: Optional[str] = Field(None, max_length=2000)
    edits: Optional[dict] = None


class BulkReviewBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    decision: Literal["confirm", "reject"]
    note: Optional[str] = Field(None, max_length=2000)


class LinkBody(BaseModel):
    relation: Literal["addresses", "evidences"]
    from_type: Literal["control", "document"]
    from_id: str = Field(min_length=1, max_length=100)
    to_type: Literal["obligation", "control"]
    to_id: str = Field(min_length=1, max_length=100)
    attributes: Optional[dict] = None
    note: Optional[str] = Field(None, max_length=2000)


class ControlBody(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    summary: Optional[str] = Field(None, max_length=1000)
    frequency: Optional[str] = None
    owner_user_id: Optional[str] = None
    owner_team: Optional[str] = Field(None, max_length=120)
    evidence_expected: Optional[str] = Field(None, max_length=300)
    topics: Optional[list[str]] = None
    document_id: Optional[str] = None
    quote: Optional[str] = Field(None, max_length=3000)


class ControlPatch(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    summary: Optional[str] = Field(None, max_length=1000)
    frequency: Optional[str] = None
    owner_user_id: Optional[str] = None
    owner_team: Optional[str] = Field(None, max_length=120)
    evidence_expected: Optional[str] = Field(None, max_length=300)
    topics: Optional[list[str]] = None
    status: Optional[Literal["active", "retired"]] = None


class StatusBody(BaseModel):
    applicability: Optional[Literal["applies", "not_applicable", ""]] = None
    note: Optional[str] = Field(None, max_length=2000)
    owner_user_id: Optional[str] = None
    owner_team: Optional[str] = Field(None, max_length=120)
    next_due_date: Optional[str] = None
    recurrence: Optional[str] = None


class RoleBody(BaseModel):
    role: Literal["regulation", "policy", "procedure", "evidence_record", "other"]
    note: Optional[str] = Field(None, max_length=2000)


class EffectiveBody(BaseModel):
    effective_date: Optional[str] = None
    note: Optional[str] = Field(None, max_length=2000)


class ProfileBody(BaseModel):
    category_codes: list[str] = Field(min_length=1, max_length=12)


class NoteBody(BaseModel):
    note: Optional[str] = Field(None, max_length=2000)


class ShareBody(BaseModel):
    note: str = Field(min_length=10, max_length=2000)


class BackfillBody(BaseModel):
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    force: bool = False


# ─── Reads ───────────────────────────────────────────────────────────────────


@router.get("/overview")
def overview(ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.overview, db, scope)


@router.get("/requirements")
def requirements(
    q: Optional[str] = None, regulator: Optional[str] = None, document_id: Optional[str] = None,
    topic: Optional[str] = None, category: Optional[str] = None, applicability: Optional[str] = None,
    coverage: Optional[str] = None, owner: Optional[str] = None, due_within: Optional[int] = Query(None, ge=0, le=730),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    ctx=Depends(scoped), db=Depends(get_db),
):
    scope, _user = ctx
    filters = {"q": q, "regulator": regulator, "document_id": document_id, "topic": topic, "category": category,
               "applicability": applicability, "coverage": coverage, "owner": owner, "due_within": due_within}
    return run(queries.requirements, db, scope, filters, page, page_size)


@router.get("/requirements/{lineage_id}")
def requirement(lineage_id: str, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.requirement_detail, db, scope, lineage_id)


@router.put("/requirements/{lineage_id}/status")
def requirement_status(lineage_id: str, body: StatusBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    run(review.set_requirement_status, db, scope, lineage_id, body.model_dump(exclude_unset=True))
    return run(queries.requirement_detail, db, scope, lineage_id)


@router.get("/controls")
def controls(include_retired: bool = False, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return {"items": run(queries.controls_list, db, scope, include_retired)}


@router.post("/controls")
def create_control(body: ControlBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    row = run(review.create_control, db, scope, body.model_dump(exclude_unset=True))
    return run(queries.control_detail, db, scope, row.id)


@router.get("/controls/{control_id}")
def control(control_id: str, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.control_detail, db, scope, control_id)


@router.patch("/controls/{control_id}")
def update_control(control_id: str, body: ControlPatch, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    run(review.update_control, db, scope, control_id, body.model_dump(exclude_unset=True))
    return run(queries.control_detail, db, scope, control_id)


@router.get("/documents/{document_id}")
def document(document_id: str, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.document_detail, db, scope, document_id)


@router.post("/documents/{document_id}/role")
def document_role(document_id: str, body: RoleBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    run(review.set_document_role, db, scope, document_id, body.role, body.note)
    return run(queries.document_detail, db, scope, document_id)


@router.post("/documents/{document_id}/effective-date")
def document_effective(document_id: str, body: EffectiveBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    run(review.set_effective_date, db, scope, document_id, body.effective_date, body.note)
    return run(queries.document_detail, db, scope, document_id)


@router.post("/documents/{document_id}/share-new-version")
def share_new_version(document_id: str, body: ShareBody, ctx=Depends(scoped), db=Depends(get_db)):
    """Superadmins publish a shared regulation's newer version to every workspace."""
    scope, user = ctx
    if not scope.is_superadmin:
        raise HTTPException(403, "Only the Iroko team can share library documents")
    from ingestion.workspaces import set_shared
    from services.compliance_graph.sync import _newer_unshared
    from services.compliance_graph.triggers import after_sharing_change

    newer = _newer_unshared(db, document_id)
    if not newer:
        raise HTTPException(409, "There is no newer, unshared version of this document")
    set_shared(db, user, newer, True, body.note)
    after_sharing_change(db, newer)
    db.commit()
    return {"shared_document_id": newer}


@router.get("/links/{link_id}")
def link(link_id: str, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.link_detail, db, scope, link_id)


@router.post("/links")
def create_link(body: LinkBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    row = run(review.create_link, db, scope, relation=body.relation, from_type=body.from_type, from_id=body.from_id,
              to_type=body.to_type, to_id=body.to_id, attributes=body.attributes, note=body.note)
    return run(queries.link_detail, db, scope, row.id)


@router.post("/links/{link_id}/accept-proposal")
def accept_proposal(link_id: str, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    run(review.accept_proposal, db, scope, link_id)
    return run(queries.link_detail, db, scope, link_id)


@router.get("/neighbourhood")
def neighbourhood(type: str, id: str, depth: int = Query(1, ge=1, le=2), include_suggested: bool = True,
                  ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.neighbourhood, db, scope, type, id, depth, include_suggested)


@router.get("/review-queue")
def review_queue(kind: Optional[str] = None, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.review_queue, db, scope, kind)


@router.post("/review")
def decide(body: ReviewBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    if body.kind == "link":
        row = run(review.review_link, db, scope, body.id, body.decision, body.note, body.edits)
        return run(queries.link_detail, db, scope, row.id)
    if body.kind == "requirement":
        row = run(review.review_obligation, db, scope, body.id, body.decision, body.note)
        return {"id": row.id, "review_status": row.review_status}
    row = run(review.review_control, db, scope, body.id, body.decision, body.note)
    return run(queries.control_detail, db, scope, row.id)


@router.post("/review/bulk")
def decide_bulk(body: BulkReviewBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return {"decided": run(review.bulk_review, db, scope, body.ids, body.decision, body.note)}


@router.get("/impacts")
def impacts(status: Optional[Literal["open", "acknowledged", "withdrawn"]] = None, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return {"items": run(queries.impacts, db, scope, status)}


@router.post("/impacts/{impact_id}/acknowledge")
def acknowledge(impact_id: str, body: NoteBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    row = run(review.acknowledge_impact, db, scope, impact_id, body.note)
    return queries.impact_payload(db, scope, row)


@router.get("/due")
def due(days: int = Query(30, ge=1, le=365), ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.due_items, db, scope, days=days)


@router.get("/search")
def search(q: str = Query("", max_length=200), ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return run(queries.search, db, scope, q)


@router.get("/profile")
def get_profile(ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    from services.compliance_graph import core

    profile = core.profile(db, scope.workspace_id)
    return {**profile, "labels": [taxonomy.label(c) for c in profile["category_codes"]],
            "can_edit": scope.is_admin}


@router.put("/profile")
def put_profile(body: ProfileBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    run(review.set_profile, db, scope, body.category_codes)
    return get_profile(ctx, db)


@router.get("/categories")
def categories(_ctx=Depends(scoped)):
    return {
        "declarable": [{"code": c, "label": taxonomy.label(c), "sector": taxonomy.CATEGORIES[c][1]}
                       for c in taxonomy.DECLARABLE],
        "all": [{"code": c, "label": label, "sector": sector, "groups": list(groups)}
                for c, (label, sector, groups) in taxonomy.CATEGORIES.items()],
        "groups": [{"code": g, "label": label} for g, label in taxonomy.GROUPS.items()],
        "topics": [{"code": t, "label": label} for t, label in taxonomy.TOPICS.items()],
    }


@router.get("/people")
def people(ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    return {"items": queries.people(db, scope)}


@router.get("/export.xlsx")
def export_xlsx(ctx=Depends(scoped), db=Depends(get_db)):
    scope, user = ctx
    from services.compliance_graph.export import build

    data = run(build, db, scope, generated_by=user.full_name or user.email)
    db.add(AuditLog(user_id=user.id, action="compliance_graph_export",
                    resource=f"compliance-graph/export/{scope.workspace_id}", details={"bytes": len(data)}))
    db.commit()
    filename = f"iroko-audit-pack-{datetime.utcnow().date().isoformat()}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.post("/admin/backfill")
def admin_backfill(body: BackfillBody, ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    if not scope.is_superadmin:
        if not scope.is_admin:
            raise HTTPException(403, "Only admins can queue extraction")
        if body.workspace_id and body.workspace_id != scope.workspace_id:
            raise HTTPException(403, "Admins can only queue their own workspace's documents")
        body.workspace_id = scope.workspace_id
    from services.compliance_graph.jobs import backfill

    if body.document_id:
        from services.compliance_graph.visibility import is_document_visible

        if not is_document_visible(db, scope, body.document_id):
            raise HTTPException(404, "Document not found")
    queued = backfill(db, document_id=body.document_id, workspace_id=body.workspace_id, force=body.force)
    return {"queued": queued}


@router.get("/admin/runs")
def admin_runs(ctx=Depends(scoped), db=Depends(get_db)):
    scope, _user = ctx
    if not scope.is_admin:
        raise HTTPException(403, "Only admins can see extraction runs")
    return queries.admin_runs(db, scope)
