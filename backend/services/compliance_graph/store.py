"""
Writes that never duplicate rows and never overwrite a reviewer's decision.

Re-extraction (a retry, a reindex, a prompt change) upserts by deterministic id.
Machine fields of an unreviewed row are refreshed; for a confirmed, rejected or
re-review row the new machine output is parked in `proposal` and the reviewed
state stays exactly as the reviewer left it. Manual (person-entered) links are
never rewritten by extraction.
"""

from __future__ import annotations

from models.compliance_graph import GraphEvent, Link, Obligation
from models.database import generate_id
from services.compliance_graph.common import stable_id, utcnow

REVIEWED = {"confirmed", "rejected", "needs_re_review"}


def event(db, subject_type, subject_id, action, *, workspace_id=None, actor=None, from_status=None,
          to_status=None, note=None, snapshot=None) -> None:
    db.add(GraphEvent(
        id=generate_id(), subject_type=subject_type, subject_id=subject_id, workspace_id=workspace_id,
        action=action, from_status=from_status, to_status=to_status, actor_user_id=actor, note=note,
        snapshot=dict(snapshot or {}), created_at=utcnow(),
    ))


def link_id(relation, from_type, from_id, to_type, to_id, workspace_id=None) -> str:
    return stable_id("link", relation, from_type, from_id, to_type, to_id, workspace_id or "")


def get_current(db, model, key):
    """db.get that also sees rows added earlier in this session.

    The API's SessionLocal does not autoflush, so without this a second upsert of
    the same id in one transaction (an Act named twice in a sentence) would insert
    a duplicate primary key.
    """
    if not db.autoflush and db.new:
        db.flush()
    return db.get(model, key)


def upsert_link(db, *, relation, layer, from_type, from_id, to_type, to_id, basis, workspace_id=None,
                anchors=(), attributes=None, rationale=None, from_document_id=None, to_document_id=None,
                run_id=None, created_by=None) -> tuple[Link, bool]:
    lid = link_id(relation, from_type, from_id, to_type, to_id, workspace_id)
    row = get_current(db, Link, lid)
    machine = {"basis": basis, "anchors": list(anchors or ()), "attributes": dict(attributes or {}),
               "rationale": rationale}
    if row is None:
        row = Link(
            id=lid, workspace_id=workspace_id, layer=layer, relation=relation, from_type=from_type,
            from_id=from_id, to_type=to_type, to_id=to_id, from_document_id=from_document_id,
            to_document_id=to_document_id, basis=basis, review_status="proposed",
            anchors=machine["anchors"], attributes=machine["attributes"], rationale=rationale,
            status="active", run_id=run_id, created_by=created_by, created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(row)
        event(db, "link", lid, f"{basis}_{relation}", workspace_id=workspace_id, actor=created_by,
              to_status="proposed", snapshot={k: v for k, v in machine.items() if k != "anchors"})
        return row, True
    if row.basis == "manual" and basis != "manual":
        return row, False
    if row.review_status in REVIEWED:
        current = {"basis": row.basis, "anchors": row.anchors, "attributes": row.attributes,
                   "rationale": row.rationale}
        if current != machine:
            row.proposal = machine
    else:
        row.basis = basis
        row.anchors = machine["anchors"]
        row.attributes = machine["attributes"]
        row.rationale = rationale
    if row.status != "active":
        event(db, "link", lid, "restored", workspace_id=workspace_id, from_status=row.status, to_status="active")
    row.status = "active"
    row.run_id = run_id
    row.from_document_id = from_document_id or row.from_document_id
    row.to_document_id = to_document_id or row.to_document_id
    row.updated_at = utcnow()
    return row, False


def withdraw_untouched_links(db, query, run_id, reason) -> int:
    """Links the latest extraction no longer produced. Reviewed ones only get a proposal."""
    count = 0
    for row in query.filter(Link.status == "active", Link.basis != "manual"):
        if row.run_id == run_id:
            continue
        if row.review_status in REVIEWED:
            row.proposal = {"withdraw": True, "reason": reason}
        else:
            row.status = "withdrawn"
            event(db, "link", row.id, "withdrawn", workspace_id=row.workspace_id, from_status="active",
                  to_status="withdrawn", note=reason)
            count += 1
    return count


OBLIGATION_MACHINE_FIELDS = (
    "summary", "kind", "addressee_span", "addressee_codes", "addressee_basis", "deadline_span", "deadline_rule",
    "frequency", "effective_span", "effective_date", "topics",
)
OBLIGATION_ANCHOR_FIELDS = (
    "quote", "page_number", "page_position", "locator", "page_char_start", "page_char_end", "chunk_id",
    "section_heading", "position", "occurrence", "text_hash", "document_id",
)


def _jsonable(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def upsert_obligation(db, values: dict, run_id) -> tuple[Obligation, bool]:
    row = get_current(db, Obligation, values["id"])
    if row is None:
        row = Obligation(id=values["id"], lineage_id=values.get("lineage_id") or values["id"],
                         review_status="proposed", status="active", run_id=run_id,
                         created_at=utcnow(), updated_at=utcnow())
        for name in OBLIGATION_ANCHOR_FIELDS + OBLIGATION_MACHINE_FIELDS:
            if name in values:
                setattr(row, name, values[name])
        db.add(row)
        event(db, "obligation", row.id, "extracted", to_status="proposed",
              snapshot={"quote": row.quote, "summary": row.summary})
        return row, True
    for name in OBLIGATION_ANCHOR_FIELDS:
        if name in values:
            setattr(row, name, values[name])
    if values.get("lineage_id") and row.lineage_id != values["lineage_id"] and row.review_status not in REVIEWED:
        row.lineage_id = values["lineage_id"]
    machine = {name: _jsonable(values.get(name)) for name in OBLIGATION_MACHINE_FIELDS if name in values}
    if row.review_status in REVIEWED:
        current = {name: _jsonable(getattr(row, name)) for name in machine}
        if current != machine:
            row.proposal = machine
    else:
        for name in machine:
            setattr(row, name, values[name])
    if row.status != "active":
        event(db, "obligation", row.id, "restored", from_status=row.status, to_status="active")
    row.status = "active"
    row.run_id = run_id
    row.updated_at = utcnow()
    return row, False


def withdraw_untouched_obligations(db, document_id, run_id) -> int:
    count = 0
    for row in db.query(Obligation).filter(Obligation.document_id == document_id, Obligation.status == "active"):
        if row.run_id == run_id:
            continue
        if row.review_status in REVIEWED:
            row.proposal = {"withdraw": True, "reason": "Not found as a requirement in the latest extraction"}
        else:
            row.status = "withdrawn"
            event(db, "obligation", row.id, "withdrawn", from_status="active", to_status="withdrawn",
                  note="Not found as a requirement in the latest extraction")
            count += 1
    return count
