"""
Decisions and edits people make to the graph.

Every change: a permission check (permissions.py), a row lock, an append-only
cg_events row, an AuditLog entry, and the follow-up sync it needs. Nothing a
model produced counts as confirmed until a person with the right role says so.
No fastapi here: routes/compliance_graph.py maps the exceptions to HTTP.
"""

from __future__ import annotations

from datetime import date

from ingestion.db import prepare_session
from ingestion.models import DocumentAccess, Page
from models.compliance_graph import (ChangeEvent, Control, GraphDocument, Impact, InstitutionProfile, Link,
                                     Obligation, ObligationStatus)
from models.database import AuditLog, Document, generate_id
from services.compliance_graph import common, store, taxonomy, triggers
from services.compliance_graph.permissions import (GraphInvalid, GraphNotFound, GraphPermissionError,
                                                   can_review_library, is_workspace_admin, require_library_reviewer,
                                                   require_member, require_proposer, require_workspace_admin)
from services.compliance_graph.visibility import (Scope, control_visible, document_visible, is_document_visible,
                                                  lineage_visible, link_visible, obligation_visible)

DECISIONS = {"confirm": "confirmed", "reject": "rejected", "reopen": "proposed"}
LIBRARY_RELATIONS = {"amends", "supersedes", "revokes", "extends_deadline_of", "references", "issued_under"}
CHANGE_RELATIONS = {"amends", "supersedes", "revokes", "extends_deadline_of"}
FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "semiannual", "annual", "event", "once")
RECURRENCES = ("monthly", "quarterly", "semiannual", "annual")


def _audit(db, scope: Scope, action: str, resource: str, details: dict | None = None) -> None:
    db.add(AuditLog(user_id=scope.user_id, action=action, resource=resource, details=dict(details or {})))


def _note(note, *, required=False) -> str | None:
    text = " ".join(str(note or "").split())[:2000]
    if required and len(text) < 5:
        raise GraphInvalid("Add a short note (at least five characters) saying why")
    return text or None


# ─── Links ───────────────────────────────────────────────────────────────────


def _locked_link(db, scope: Scope, link_id: str) -> Link:
    row = db.query(Link).filter(Link.id == link_id, link_visible(scope, Link)).with_for_update().first()
    if row is None:
        raise GraphNotFound("That link is not available")
    return row


def _documents_of(link: Link) -> list[str]:
    return [d for d in (link.from_document_id, link.to_document_id) if d]


def _check_link_reviewer(db, scope: Scope, link: Link) -> None:
    if link.layer == "library":
        require_library_reviewer(db, scope, _documents_of(link))
    else:
        require_workspace_admin(scope, link.workspace_id)


def _apply_decision(db, scope: Scope, row: Link, decision: str, note: str | None, edits: dict) -> Link:
    before = row.review_status
    changed = {}
    coverage = edits.get("coverage")
    if coverage is not None:
        if row.relation not in ("addresses", "evidences") or coverage not in ("full", "partial"):
            raise GraphInvalid("Coverage applies to control and evidence links and must be full or partial")
        changed["coverage"] = coverage
    for name in ("period_start", "period_end"):
        if name in edits:
            if row.relation != "evidences":
                raise GraphInvalid("A period applies to evidence links only")
            value = common.parse_iso_date(edits[name])
            if edits[name] and value is None:
                raise GraphInvalid(f"{name} must be a date (YYYY-MM-DD)")
            changed[name] = value.isoformat() if value else None
    if changed:
        row.attributes = {**(row.attributes or {}), **changed}
    row.review_status = DECISIONS[decision]
    row.reviewed_by, row.reviewed_at, row.review_note = scope.user_id, common.utcnow(), note
    if row.review_status == "confirmed":
        row.stale_reason = None
    store.event(db, "link", row.id, f"review_{decision}", workspace_id=row.workspace_id, actor=scope.user_id,
                from_status=before, to_status=row.review_status, note=note, snapshot={"edits": changed})
    _audit(db, scope, f"graph_link_{decision}", f"compliance-graph/links/{row.id}",
           {"relation": row.relation, "from": before, "to": row.review_status, "note": note, "edits": changed})
    return row


def _after_link_review(db, row: Link) -> None:
    if row.layer == "library":
        if row.relation in CHANGE_RELATIONS and row.to_type == "document":
            from services.compliance_graph.jobs import record_change_event

            if row.review_status == "confirmed" or (row.basis == "stated" and row.review_status != "rejected"):
                source = db.get(Document, row.from_id)
                record_change_event(db, row, source.title if source else row.from_id)
            elif row.review_status == "rejected":
                event = db.get(ChangeEvent, common.stable_id("change", row.id))
                if event is not None:
                    event.status = "withdrawn"
        triggers.after_library_review(db, _documents_of(row))
    else:
        triggers.enqueue_workspace(db, row.workspace_id)


def review_link(db, scope: Scope, link_id: str, decision: str, note=None, edits=None) -> Link:
    prepare_session(db)
    if decision not in DECISIONS:
        raise GraphInvalid("Decision must be confirm, reject or reopen")
    note = _note(note, required=decision == "reject")
    edits = dict(edits or {})
    row = _locked_link(db, scope, link_id)
    _check_link_reviewer(db, scope, row)
    new_relation = edits.pop("relation", None)
    if new_relation and new_relation != row.relation:
        # Correcting what kind of relationship it is: the reviewer's version replaces Iroko's.
        if row.layer != "library" or new_relation not in LIBRARY_RELATIONS:
            raise GraphInvalid("Only regulation relationships can be re-typed")
        replacement, _created = store.upsert_link(
            db, relation=new_relation, layer="library", from_type=row.from_type, from_id=row.from_id,
            to_type=row.to_type, to_id=row.to_id, basis="manual", anchors=row.anchors,
            attributes=row.attributes, rationale=None, from_document_id=row.from_document_id,
            to_document_id=row.to_document_id, created_by=scope.user_id)
        _apply_decision(db, scope, row, "reject", note or f"Corrected to {new_relation}", {})
        _after_link_review(db, row)
        _apply_decision(db, scope, replacement, "confirm", note, edits)
        _after_link_review(db, replacement)
        db.commit()
        return replacement
    _apply_decision(db, scope, row, decision, note, edits)
    _after_link_review(db, row)
    db.commit()
    return row


def bulk_review(db, scope: Scope, link_ids, decision: str, note=None) -> int:
    """Bulk confirm is for facts stated in the source; anything can be bulk-rejected with a note."""
    prepare_session(db)
    if decision not in ("confirm", "reject"):
        raise GraphInvalid("Bulk decisions are confirm or reject")
    note = _note(note, required=decision == "reject")
    done = 0
    for link_id in list(dict.fromkeys(link_ids or ()))[:200]:
        row = _locked_link(db, scope, link_id)
        _check_link_reviewer(db, scope, row)
        if decision == "confirm" and row.basis != "stated" and row.relation != "applies_to":
            raise GraphInvalid("Only facts stated in the source can be confirmed in bulk; review suggestions one by one")
        _apply_decision(db, scope, row, decision, note, {})
        _after_link_review(db, row)
        done += 1
    db.commit()
    return done


def accept_proposal(db, scope: Scope, link_id: str) -> Link:
    """Adopt Iroko's newer reading of an already reviewed link."""
    prepare_session(db)
    row = _locked_link(db, scope, link_id)
    _check_link_reviewer(db, scope, row)
    proposal = row.proposal or {}
    if not proposal:
        raise GraphInvalid("There is no newer reading to accept")
    if proposal.get("withdraw"):
        row.status = "withdrawn"
    else:
        row.basis = proposal.get("basis", row.basis)
        row.anchors = proposal.get("anchors", row.anchors)
        row.attributes = proposal.get("attributes", row.attributes)
        row.rationale = proposal.get("rationale", row.rationale)
    row.proposal = None
    store.event(db, "link", row.id, "proposal_accepted", workspace_id=row.workspace_id, actor=scope.user_id,
                snapshot=proposal)
    _audit(db, scope, "graph_link_proposal_accepted", f"compliance-graph/links/{row.id}")
    _after_link_review(db, row)
    db.commit()
    return row


def create_link(db, scope: Scope, *, relation, from_type, from_id, to_type, to_id, attributes=None, note=None) -> Link:
    """A person connects a control or record to a requirement (or a record to a control)."""
    prepare_session(db)
    require_proposer(scope)
    note = _note(note)
    attributes = dict(attributes or {})
    ws = scope.workspace_id
    if relation == "addresses":
        if from_type != "control" or to_type != "obligation":
            raise GraphInvalid("A control addresses a requirement")
    elif relation == "evidences":
        if from_type != "document" or to_type not in ("control", "obligation"):
            raise GraphInvalid("An evidence record supports a control or a requirement")
    else:
        raise GraphInvalid("You can link controls and evidence only")
    anchors, from_doc, to_doc = [], None, None
    if from_type == "control":
        control = db.query(Control).filter(Control.id == from_id, Control.status == "active",
                                           control_visible(scope, Control)).first()
        if control is None:
            raise GraphNotFound("That control is not available")
        from_doc = control.document_id
        anchors.append({"kind": "control", "side": "from", "control_id": control.id, "document_id": control.document_id,
                        "quote": control.quote or control.name, "page_number": control.page_number,
                        "start": control.page_char_start, "end": control.page_char_end})
    else:
        access = db.get(DocumentAccess, from_id)
        if access is None or access.workspace_id != ws or not is_document_visible(db, scope, from_id):
            raise GraphNotFound("That record is not one of your workspace's documents")
        from_doc = from_id
        anchors.append({"kind": "evidence", "side": "from", "document_id": from_id})
    if to_type == "obligation":
        obligation = (db.query(Obligation)
                      .filter(Obligation.lineage_id == to_id, obligation_visible(scope, Obligation, current=True))
                      .first())
        if obligation is None:
            raise GraphNotFound("That requirement is not available")
        to_doc = obligation.document_id
        anchors.append({"kind": "obligation", "side": "to", "obligation_id": obligation.id,
                        "document_id": obligation.document_id, "quote": obligation.quote,
                        "page_number": obligation.page_number, "start": obligation.page_char_start,
                        "end": obligation.page_char_end, "chunk_id": obligation.chunk_id})
    else:
        target = db.query(Control).filter(Control.id == to_id, Control.status == "active",
                                          control_visible(scope, Control)).first()
        if target is None:
            raise GraphNotFound("That control is not available")
        to_doc = target.document_id
        anchors.append({"kind": "control", "side": "to", "control_id": target.id, "document_id": target.document_id,
                        "quote": target.quote or target.name})
    if attributes.get("coverage") not in (None, "full", "partial"):
        raise GraphInvalid("Coverage must be full or partial")
    clean = {k: v for k, v in attributes.items() if k in ("coverage", "period_start", "period_end")}
    lid = store.link_id(relation, from_type, from_id, to_type, to_id, ws)
    existing = db.query(Link).filter(Link.id == lid).with_for_update().first()
    admin = is_workspace_admin(scope, ws)
    if existing is not None and existing.status == "active":
        decision = "confirm" if admin else "reopen"
        if existing.review_status == ("confirmed" if admin else "proposed"):
            return existing
        _apply_decision(db, scope, existing, decision, note, clean)
        triggers.enqueue_workspace(db, ws)
        db.commit()
        return existing
    row, _created = store.upsert_link(
        db, relation=relation, layer="workspace", workspace_id=ws, from_type=from_type, from_id=from_id,
        to_type=to_type, to_id=to_id, basis="manual", anchors=anchors, attributes={"coverage": "full", **clean},
        from_document_id=from_doc, to_document_id=to_doc, created_by=scope.user_id)
    row.basis, row.status, row.created_by = "manual", "active", scope.user_id
    if admin:
        row.review_status, row.reviewed_by, row.reviewed_at, row.review_note = "confirmed", scope.user_id, common.utcnow(), note
    _audit(db, scope, "graph_link_created", f"compliance-graph/links/{row.id}", {"relation": relation, "note": note})
    triggers.enqueue_workspace(db, ws)
    db.commit()
    return row


# ─── Requirements, documents and dates (library facts) ──────────────────────


def review_obligation(db, scope: Scope, obligation_id: str, decision: str, note=None) -> Obligation:
    prepare_session(db)
    if decision not in DECISIONS:
        raise GraphInvalid("Decision must be confirm, reject or reopen")
    note = _note(note, required=decision == "reject")
    row = (db.query(Obligation)
           .filter(Obligation.id == obligation_id, obligation_visible(scope, Obligation, current=False))
           .with_for_update().first())
    if row is None:
        raise GraphNotFound("That requirement is not available")
    require_library_reviewer(db, scope, [row.document_id])
    before = row.review_status
    row.review_status = DECISIONS[decision]
    row.reviewed_by, row.reviewed_at, row.review_note = scope.user_id, common.utcnow(), note
    store.event(db, "obligation", row.id, f"review_{decision}", actor=scope.user_id, from_status=before,
                to_status=row.review_status, note=note)
    _audit(db, scope, f"graph_requirement_{decision}", f"compliance-graph/requirements/{row.lineage_id}",
           {"note": note})
    triggers.after_library_review(db, [row.document_id])
    db.commit()
    return row


def _locked_document(db, scope: Scope, document_id: str) -> GraphDocument:
    if not is_document_visible(db, scope, document_id, current=False):
        raise GraphNotFound("That document is not available")
    gd = db.query(GraphDocument).filter(GraphDocument.document_id == document_id).with_for_update().first()
    if gd is None:
        gd = GraphDocument(document_id=document_id, stage_state={}, facts={}, role="other", role_basis="suggested",
                           extraction_status="pending")
        db.add(gd)
    return gd


def set_document_role(db, scope: Scope, document_id: str, role: str, note=None) -> GraphDocument:
    from services.compliance_graph.extract import ROLES

    prepare_session(db)
    if role not in ROLES:
        raise GraphInvalid(f"Role must be one of: {', '.join(ROLES)}")
    gd = _locked_document(db, scope, document_id)
    access = db.get(DocumentAccess, document_id)
    doc = db.get(Document, document_id)
    if access is not None and access.shared_regulatory:
        if not scope.is_superadmin:
            raise GraphPermissionError("Roles of shared library documents are set by the Iroko team")
    elif not (is_workspace_admin(scope, access.workspace_id if access else None)
              or (doc is not None and doc.uploaded_by_id == scope.user_id and scope.role != "viewer")):
        raise GraphPermissionError("Only the uploader or an admin of this workspace can set its role")
    before = gd.role
    gd.role, gd.role_basis, gd.role_suggestion = role, "confirmed", None
    store.event(db, "document", document_id, "role_set", workspace_id=access.workspace_id if access else None,
                actor=scope.user_id, from_status=before, to_status=role, note=_note(note))
    _audit(db, scope, "graph_document_role_set", f"documents/{document_id}", {"from": before, "to": role})
    if before != role:
        gd.stage_state = {}
        triggers.enqueue_document(db, document_id)
    db.commit()
    return gd


def set_effective_date(db, scope: Scope, document_id: str, effective, note=None) -> GraphDocument:
    prepare_session(db)
    gd = _locked_document(db, scope, document_id)
    require_library_reviewer(db, scope, [document_id])
    value = common.parse_iso_date(effective) if effective else None
    if effective and value is None:
        raise GraphInvalid("The effective date must be a date (YYYY-MM-DD)")
    before = gd.effective_date.isoformat() if gd.effective_date else None
    gd.effective_date, gd.effective_basis = value, "confirmed"
    store.event(db, "document", document_id, "effective_date_confirmed", actor=scope.user_id, from_status=before,
                to_status=value.isoformat() if value else None, note=_note(note))
    _audit(db, scope, "graph_effective_date_confirmed", f"documents/{document_id}",
           {"effective_date": value.isoformat() if value else None})
    triggers.after_library_review(db, [document_id])
    db.commit()
    return gd


# ─── Controls ────────────────────────────────────────────────────────────────


def _clean_control_fields(db, scope: Scope, values: dict) -> dict:
    out = {}
    for name in ("name", "summary", "owner_team", "evidence_expected"):
        if name in values:
            text = " ".join(str(values[name] or "").split())
            out[name] = text[:300] or None
    if "name" in out and not out["name"]:
        raise GraphInvalid("A control needs a name")
    if "frequency" in values:
        if values["frequency"] not in (None, "", *FREQUENCIES):
            raise GraphInvalid(f"Frequency must be one of: {', '.join(FREQUENCIES)}")
        out["frequency"] = values["frequency"] or None
    if "topics" in values:
        out["topics"] = taxonomy.valid_topics(values["topics"])
    if "owner_user_id" in values:
        require_member(db, scope, values["owner_user_id"])
        out["owner_user_id"] = values["owner_user_id"] or None
    return out


def create_control(db, scope: Scope, values: dict) -> Control:
    prepare_session(db)
    require_proposer(scope)
    fields = _clean_control_fields(db, scope, {"name": values.get("name"), **values})
    anchor = {}
    document_id = values.get("document_id")
    if document_id:
        access = db.get(DocumentAccess, document_id)
        if access is None or access.workspace_id != scope.workspace_id or not is_document_visible(db, scope, document_id):
            raise GraphNotFound("That policy is not one of your workspace's documents")
        anchor["document_id"] = document_id
        quote = values.get("quote")
        if quote:
            for page in db.query(Page).filter_by(document_id=document_id).order_by(Page.position):
                where = common.locate(quote, page.text or "")
                if where:
                    anchor.update(quote=" ".join(page.text[where[0]:where[1]].split()), page_number=page.page_number,
                                  page_position=page.position, page_char_start=where[0], page_char_end=where[1])
                    break
            else:
                raise GraphInvalid("That wording was not found in the policy; copy it exactly")
    admin = is_workspace_admin(scope, scope.workspace_id)
    text = anchor.get("quote") or f"{fields.get('name')} {fields.get('summary') or ''}"
    row = Control(id=generate_id(), workspace_id=scope.workspace_id, basis="manual",
                  review_status="confirmed" if admin else "proposed", status="active", anchor_history=[],
                  text_hash=common.text_hash(text), created_by=scope.user_id, topics=fields.pop("topics", []),
                  created_at=common.utcnow(), updated_at=common.utcnow(), **fields, **anchor)
    if admin:
        row.reviewed_by, row.reviewed_at = scope.user_id, common.utcnow()
    db.add(row)
    store.event(db, "control", row.id, "created", workspace_id=scope.workspace_id, actor=scope.user_id,
                to_status=row.review_status, snapshot={"name": row.name})
    _audit(db, scope, "graph_control_created", f"compliance-graph/controls/{row.id}", {"name": row.name})
    triggers.enqueue_workspace(db, scope.workspace_id)
    db.commit()
    return row


def _locked_control(db, scope: Scope, control_id: str) -> Control:
    row = db.query(Control).filter(Control.id == control_id, control_visible(scope, Control)).with_for_update().first()
    if row is None:
        raise GraphNotFound("That control is not available")
    return row


def update_control(db, scope: Scope, control_id: str, values: dict) -> Control:
    prepare_session(db)
    row = _locked_control(db, scope, control_id)
    admin = is_workspace_admin(scope, row.workspace_id)
    if not admin and not (scope.role == "analyst" and row.created_by == scope.user_id and row.review_status == "proposed"):
        raise GraphPermissionError("Only an admin of this workspace can change this control")
    fields = _clean_control_fields(db, scope, values)
    if "status" in values:
        if values["status"] not in ("active", "retired"):
            raise GraphInvalid("Status must be active or retired")
        fields["status"] = values["status"]
    before = {k: getattr(row, k) for k in fields}
    for name, value in fields.items():
        setattr(row, name, value)
    row.updated_at = common.utcnow()
    store.event(db, "control", row.id, "edited", workspace_id=row.workspace_id, actor=scope.user_id,
                snapshot={"before": {k: str(v) for k, v in before.items()}, "after": {k: str(v) for k, v in fields.items()}})
    _audit(db, scope, "graph_control_edited", f"compliance-graph/controls/{row.id}", {"fields": sorted(fields)})
    triggers.enqueue_workspace(db, row.workspace_id)
    db.commit()
    return row


def review_control(db, scope: Scope, control_id: str, decision: str, note=None) -> Control:
    prepare_session(db)
    if decision not in DECISIONS:
        raise GraphInvalid("Decision must be confirm, reject or reopen")
    note = _note(note, required=decision == "reject")
    row = _locked_control(db, scope, control_id)
    require_workspace_admin(scope, row.workspace_id)
    before = row.review_status
    row.review_status = DECISIONS[decision]
    row.reviewed_by, row.reviewed_at, row.review_note = scope.user_id, common.utcnow(), note
    store.event(db, "control", row.id, f"review_{decision}", workspace_id=row.workspace_id, actor=scope.user_id,
                from_status=before, to_status=row.review_status, note=note)
    _audit(db, scope, f"graph_control_{decision}", f"compliance-graph/controls/{row.id}", {"note": note})
    triggers.enqueue_workspace(db, row.workspace_id)
    db.commit()
    return row


# ─── Workspace decisions ─────────────────────────────────────────────────────


def set_requirement_status(db, scope: Scope, lineage_id: str, values: dict) -> ObligationStatus:
    prepare_session(db)
    require_workspace_admin(scope, scope.workspace_id)
    visible = db.query(Obligation.id).filter(Obligation.lineage_id == lineage_id,
                                             lineage_visible(scope, Obligation.lineage_id)).first()
    if visible is None:
        raise GraphNotFound("That requirement is not available")
    row = (db.query(ObligationStatus)
           .filter(ObligationStatus.workspace_id == scope.workspace_id, ObligationStatus.lineage_id == lineage_id)
           .with_for_update().first())
    if row is None:
        row = ObligationStatus(workspace_id=scope.workspace_id, lineage_id=lineage_id)
        db.add(row)
    changes = {}
    if "applicability" in values:
        decision = values["applicability"] or None
        if decision not in (None, "applies", "not_applicable"):
            raise GraphInvalid("Applicability must be applies, not_applicable or empty")
        note = _note(values.get("note"), required=decision == "not_applicable")
        row.applicability_decision, row.applicability_note = decision, note
        row.decided_by, row.decided_at = scope.user_id, common.utcnow()
        changes["applicability"] = decision
    if "owner_user_id" in values:
        require_member(db, scope, values["owner_user_id"])
        row.owner_user_id = values["owner_user_id"] or None
        changes["owner_user_id"] = row.owner_user_id
    if "owner_team" in values:
        row.owner_team = (" ".join(str(values["owner_team"] or "").split())[:120]) or None
        changes["owner_team"] = row.owner_team
    if "next_due_date" in values:
        due = common.parse_iso_date(values["next_due_date"]) if values["next_due_date"] else None
        if values["next_due_date"] and due is None:
            raise GraphInvalid("The due date must be a date (YYYY-MM-DD)")
        row.next_due_date, row.due_basis = due, "owner" if due else None
        changes["next_due_date"] = due.isoformat() if due else None
    if "recurrence" in values:
        if values["recurrence"] not in (None, "", *RECURRENCES):
            raise GraphInvalid(f"Recurrence must be one of: {', '.join(RECURRENCES)}")
        row.recurrence = values["recurrence"] or None
        changes["recurrence"] = row.recurrence
    row.updated_by, row.updated_at = scope.user_id, common.utcnow()
    store.event(db, "obligation_status", lineage_id, "workspace_decision", workspace_id=scope.workspace_id,
                actor=scope.user_id, note=row.applicability_note, snapshot=changes)
    _audit(db, scope, "graph_requirement_status", f"compliance-graph/requirements/{lineage_id}", changes)
    triggers.enqueue_workspace(db, scope.workspace_id)
    db.commit()
    return row


def set_profile(db, scope: Scope, codes) -> InstitutionProfile:
    prepare_session(db)
    require_workspace_admin(scope, scope.workspace_id)
    chosen = [c for c in dict.fromkeys(codes or ()) if c in taxonomy.DECLARABLE]
    if not chosen or len(chosen) != len(list(dict.fromkeys(codes or ()))):
        raise GraphInvalid(f"Choose one or more of: {', '.join(taxonomy.DECLARABLE)}")
    row = db.query(InstitutionProfile).filter(InstitutionProfile.workspace_id == scope.workspace_id).with_for_update().first()
    if row is None:
        row = InstitutionProfile(workspace_id=scope.workspace_id)
        db.add(row)
    before = list(row.category_codes or [])
    row.category_codes, row.basis, row.updated_by, row.updated_at = chosen, "confirmed", scope.user_id, common.utcnow()
    store.event(db, "profile", scope.workspace_id, "licence_categories_set", workspace_id=scope.workspace_id,
                actor=scope.user_id, snapshot={"before": before, "after": chosen})
    _audit(db, scope, "graph_profile_set", f"compliance-graph/profile/{scope.workspace_id}", {"categories": chosen})
    triggers.enqueue_workspace(db, scope.workspace_id)
    db.commit()
    return row


def acknowledge_impact(db, scope: Scope, impact_id: str, note=None) -> Impact:
    from services.workflow_service import close_graph_task

    prepare_session(db)
    require_workspace_admin(scope, scope.workspace_id)
    row = (db.query(Impact).filter(Impact.id == impact_id, Impact.workspace_id == scope.workspace_id)
           .with_for_update().first())
    if row is None:
        raise GraphNotFound("That change is not available")
    if row.status == "open":
        row.status, row.acknowledged_by, row.acknowledged_at = "acknowledged", scope.user_id, common.utcnow()
        close_graph_task(db, "change_impact", row.id)
        store.event(db, "impact", row.id, "acknowledged", workspace_id=scope.workspace_id, actor=scope.user_id,
                    from_status="open", to_status="acknowledged", note=_note(note))
        _audit(db, scope, "graph_impact_acknowledged", f"compliance-graph/impacts/{row.id}")
        db.commit()
    return row


def can_review(db, scope: Scope, link: Link) -> bool:
    """Whether the caller may decide on this link (used to show or hide actions)."""
    if link.layer == "library":
        try:
            return can_review_library(db, scope, _documents_of(link))
        except Exception:
            return False
    return is_workspace_admin(scope, link.workspace_id)


def as_date(value) -> date | None:
    return common.parse_iso_date(value)
