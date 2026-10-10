"""
Read models for the API, chat and the audit export.

Every list starts from visibility.py's predicates for the caller's workspace;
applicability, coverage and due dates are computed per request from stored
facts and explicit decisions. Counts are taken from the same filtered sets, so
a number never includes a row the caller cannot open.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from ingestion.db import prepare_session
from ingestion.models import DocumentAccess, Membership, Revision
from models.compliance_graph import (ChangeEvent, Control, GraphDocument, GraphEvent, GraphRun, Impact, Link,
                                     Obligation)
from models.database import Document, User
from services.compliance_graph import applicability, core, deadlines, taxonomy
from services.compliance_graph.common import lagos_today
from services.compliance_graph.permissions import GraphNotFound, can_review_library, is_workspace_admin
from services.compliance_graph.visibility import (Scope, awaiting_publication, control_visible, document_visible,
                                                  is_document_visible, link_visible, obligation_visible)

BASIS_LABELS = {"stated": "Stated in source", "suggested": "Suggested by Iroko", "manual": "Entered by a person",
                "inherited": "From the document's addressees"}
REVIEW_LABELS = {"proposed": "Awaiting review", "confirmed": "Confirmed", "rejected": "Rejected",
                 "needs_re_review": "Needs re-review"}
RELATION_LABELS = {
    "amends": "amends", "supersedes": "supersedes", "revokes": "revokes", "extends_deadline_of": "extends a deadline in",
    "references": "cites", "issued_under": "is issued under", "applies_to": "is addressed to",
    "filed_via": "is reported through", "addresses": "addresses", "evidences": "is evidence for",
}
ROLE_LABELS = {"regulation": "Regulation or guidance", "policy": "Policy", "procedure": "Procedure",
               "evidence_record": "Evidence record", "other": "Other"}


def _iso(value):
    return value.isoformat() if value else None


def names(db, user_ids) -> dict[str, str]:
    ids = [i for i in set(user_ids or ()) if i]
    if not ids:
        return {}
    return {u.id: (u.full_name or u.email) for u in db.query(User).filter(User.id.in_(ids))}


def status_payload(row, people: dict) -> dict:
    """basis + review state, labelled the way the UI and export show them."""
    basis, review = row.basis if hasattr(row, "basis") else None, row.review_status
    reviewer = people.get(getattr(row, "reviewed_by", None))
    created_by = people.get(getattr(row, "created_by", None))
    if review == "confirmed":
        when = getattr(row, "reviewed_at", None)
        label = f"Confirmed by {reviewer or 'a reviewer'}" + (f" on {when.date().isoformat()}" if when else "")
    elif review == "rejected":
        label = f"Rejected by {reviewer or 'a reviewer'}"
    elif review == "needs_re_review":
        label = f"Needs re-review: {getattr(row, 'stale_reason', None) or 'something it relied on changed'}"
    elif basis == "manual":
        label = f"Entered by {created_by or 'a person'} — awaiting review"
    else:
        label = f"{BASIS_LABELS.get(basis, 'Suggested by Iroko')} — awaiting review"
    return {"basis": basis, "basis_label": BASIS_LABELS.get(basis), "review_status": review,
            "review_label": REVIEW_LABELS.get(review), "label": label, "reviewed_by": reviewer,
            "reviewed_at": _iso(getattr(row, "reviewed_at", None)), "review_note": getattr(row, "review_note", None)}


def document_info(db, scope: Scope, document_ids) -> dict[str, dict]:
    ids = [d for d in set(document_ids or ()) if d]
    if not ids:
        return {}
    docs = {d.id: d for d in db.query(Document).filter(Document.id.in_(ids))}
    graph = {g.document_id: g for g in db.query(GraphDocument).filter(GraphDocument.document_id.in_(ids))}
    access = {a.document_id: a for a in db.query(DocumentAccess).filter(DocumentAccess.document_id.in_(ids))}
    out = {}
    for document_id in ids:
        doc, gd, acc = docs.get(document_id), graph.get(document_id), access.get(document_id)
        if doc is None:
            continue
        out[document_id] = {
            "id": document_id, "title": doc.title, "status": doc.status,
            "role": gd.role if gd else None, "role_label": ROLE_LABELS.get(gd.role) if gd else None,
            "role_basis": gd.role_basis if gd else None, "role_suggestion": gd.role_suggestion if gd else None,
            "regulator": gd.regulator if gd else None, "reference": gd.reference_number if gd else None,
            "published_date": _iso(gd.published_date) if gd else None,
            "effective_date": _iso(gd.effective_date) if gd else None,
            "effective_basis": gd.effective_basis if gd else None,
            "shared": bool(acc and acc.shared_regulatory),
            "awaiting_publication": doc.status == "superseded" and awaiting_publication(db, scope, document_id),
            "extraction_status": gd.extraction_status if gd else None,
        }
    return out


def anchor_payload(anchor: dict, docs: dict[str, dict]) -> dict:
    info = docs.get(anchor.get("document_id")) or {}
    return {**anchor, "document_title": info.get("title"), "reference": info.get("reference"),
            "published_date": info.get("published_date"), "effective_date": info.get("effective_date"),
            "effective_basis": info.get("effective_basis"),
            "awaiting_publication": info.get("awaiting_publication", False)}


# ─── Requirements ────────────────────────────────────────────────────────────


def _due_for(o: Obligation, decision, today: date) -> dict:
    if decision is not None and decision.next_due_date:
        due = decision.next_due_date
        while due < today and decision.recurrence:
            due = deadlines.recurrence_after(due, decision.recurrence)
        return {"date": _iso(due), "basis": "owner", "description": "Date set by your team"}
    rule = o.deadline_rule
    due = deadlines.next_due(rule, today)
    if due:
        return {"date": _iso(due), "basis": "rule", "description": rule.get("text") if isinstance(rule, dict) else None}
    return {"date": None, "basis": "rule" if rule else None, "description": deadlines.describe(rule)}


def requirement_rows(db, scope: Scope, *, today: date | None = None, lineage_ids=None) -> list[dict]:
    """One row per current requirement. lineage_ids limits the work to those requirements (detail views)."""
    prepare_session(db)
    today = today or lagos_today()
    obligations = [o for o in core.visible_obligations(db, scope, current=True, lineage_ids=lineage_ids)
                   if o.review_status != "rejected"]
    codes = core.profile(db, scope.workspace_id)["category_codes"]
    applicable = core.applicability_of(db, scope, obligations, codes)
    lineages = [o.lineage_id for o in obligations]
    coverage = core.coverage_of(db, scope, lineages, applicable, today=today)
    decisions = core.decisions(db, scope.workspace_id, lineages)
    docs = document_info(db, scope, [o.document_id for o in obligations])
    people = names(db, [d.owner_user_id for d in decisions.values()])
    rows, seen = [], set()
    for o in obligations:
        if o.lineage_id in seen:
            continue
        seen.add(o.lineage_id)
        decision = decisions.get(o.lineage_id)
        cov = coverage.get(o.lineage_id)
        state = applicable.get(o.lineage_id, "undetermined")
        rows.append({
            "lineage_id": o.lineage_id, "id": o.id, "quote": o.quote, "summary": o.summary, "kind": o.kind,
            "topics": o.topics or [], "page_number": o.page_number, "section": o.section_heading,
            "chunk_id": o.chunk_id, "addressee_codes": o.addressee_codes or [], "addressee_basis": o.addressee_basis,
            "review_status": o.review_status,
            "document": docs.get(o.document_id, {"id": o.document_id}),
            "applicability": {"state": state, "label": applicability.LABELS[state],
                              "note": decision.applicability_note if decision else None},
            "coverage": {
                "state": cov.state if cov else "no_control_linked",
                "label": core.COVERAGE_LABELS.get(cov.state if cov else "no_control_linked"),
                "partial": bool(cov and cov.partial),
                "controls_confirmed": len(cov.controls_confirmed) if cov else 0,
                "controls_suggested": len(cov.controls_suggested) if cov else 0,
                "evidence_confirmed": len(cov.evidence_confirmed) if cov else 0,
                "evidence_suggested": len(cov.evidence_suggested) if cov else 0,
                "latest_evidence": _iso(cov.latest_evidence) if cov else None,
            },
            "owner": {"user_id": decision.owner_user_id if decision else None,
                      "name": people.get(decision.owner_user_id) if decision else None,
                      "team": decision.owner_team if decision else None},
            "due": _due_for(o, decision, today),
            "deadline_rule": o.deadline_rule,
        })
    return rows


def _matches(row, filters) -> bool:
    q = (filters.get("q") or "").strip().lower()
    if q:
        haystack = " ".join(str(x or "") for x in (row["quote"], row["summary"], row["document"].get("title"),
                                                   row["document"].get("reference"))).lower()
        if q not in haystack:
            return False
    if filters.get("regulator") and (row["document"].get("regulator") or "") != filters["regulator"]:
        return False
    if filters.get("document_id") and row["document"].get("id") != filters["document_id"]:
        return False
    if filters.get("topic") and filters["topic"] not in row["topics"]:
        return False
    if filters.get("category") and not (taxonomy.leaves([filters["category"]]) & taxonomy.leaves(row["addressee_codes"])):
        return False
    if filters.get("applicability"):
        wanted = set(filters["applicability"].split(","))
        if "applying" in wanted:
            wanted |= set(applicability.APPLYING_STATES)
        if row["applicability"]["state"] not in wanted:
            return False
    if filters.get("coverage") and row["coverage"]["state"] not in set(filters["coverage"].split(",")):
        return False
    owner = filters.get("owner")
    if owner == "none" and (row["owner"]["user_id"] or row["owner"]["team"]):
        return False
    if owner and owner != "none" and row["owner"]["user_id"] != owner:
        return False
    if filters.get("due_within") is not None:
        due = row["due"]["date"]
        if not due or date.fromisoformat(due) > lagos_today() + timedelta(days=int(filters["due_within"])):
            return False
    return True


def requirements(db, scope: Scope, filters: dict, page: int = 1, page_size: int = 25) -> dict:
    rows = requirement_rows(db, scope)
    facets = {
        "coverage": Counter(r["coverage"]["state"] for r in rows
                            if r["applicability"]["state"] in applicability.APPLYING_STATES),
        "applicability": Counter(r["applicability"]["state"] for r in rows),
        "regulator": Counter(r["document"].get("regulator") or "Other" for r in rows),
    }
    matched = [r for r in rows if _matches(r, filters)]
    matched.sort(key=lambda r: (r["due"]["date"] or "9999", r["document"].get("title") or "", r["id"]))
    page_size = max(1, min(int(page_size or 25), 100))
    page = max(1, int(page or 1))
    start = (page - 1) * page_size
    return {"items": matched[start:start + page_size], "total": len(matched), "page": page, "page_size": page_size,
            "facets": {k: dict(v) for k, v in facets.items()}}


# ─── Due dates ───────────────────────────────────────────────────────────────


def due_items(db, scope: Scope, *, days: int = 30, rows=None, today: date | None = None) -> dict:
    today = today or lagos_today()
    horizon = today + timedelta(days=days)
    rows = requirement_rows(db, scope, today=today) if rows is None else rows
    dated, event_driven = [], []
    for r in rows:
        if r["applicability"]["state"] not in applicability.APPLYING_STATES:
            continue
        if r["due"]["date"]:
            if date.fromisoformat(r["due"]["date"]) <= horizon:
                dated.append({"kind": "requirement", "date": r["due"]["date"], "title": r["summary"] or r["quote"][:140],
                              "lineage_id": r["lineage_id"], "basis": r["due"]["basis"],
                              "document": r["document"].get("title"), "owner": r["owner"]})
        elif isinstance(r["deadline_rule"], dict) and r["deadline_rule"].get("kind") == "within":
            event_driven.append({"lineage_id": r["lineage_id"], "title": r["summary"] or r["quote"][:140],
                                 "description": r["due"]["description"], "document": r["document"].get("title")})
    codes = core.profile(db, scope.workspace_id)["category_codes"]
    try:
        from models.filing import FilingDraft
        from services.regulatory_returns.calendar import upcoming

        submitted = {(d.return_id, d.period): d.status
                     for d in db.query(FilingDraft).filter(FilingDraft.workspace_id == scope.workspace_id)}
        for item in upcoming(today):
            if not taxonomy.return_applies(item["return_id"], codes) or item["due"] > horizon.isoformat():
                continue
            status = submitted.get((item["return_id"], item["period"]))
            if status == "submitted":
                continue
            dated.append({"kind": "return", "date": item["due"], "title": f"{item['title']} — {item['period_label']}",
                          "return_id": item["return_id"], "period": item["period"], "regulator": item["regulator"],
                          "draft_status": status})
    except Exception:  # the returns module is optional context, never a reason to fail
        pass
    for gd in db.query(GraphDocument).filter(GraphDocument.effective_date.isnot(None),
                                             GraphDocument.effective_date >= today,
                                             GraphDocument.effective_date <= horizon,
                                             document_visible(scope, GraphDocument.document_id, current=True)):
        dated.append({"kind": "effective", "date": _iso(gd.effective_date), "title": f"“{gd.title}” takes effect",
                      "document_id": gd.document_id, "basis": gd.effective_basis})
    controls = {c.id: c for c in core.active_controls(db, scope)}
    evidence_dates = defaultdict(list)
    for link in core.workspace_links(db, scope, ("evidences",)):
        if link.to_type == "control" and link.review_status == "confirmed":
            ev = core.evidence_date(db.get(GraphDocument, link.from_id))
            if ev:
                evidence_dates[link.to_id].append(ev)
    for control_id, dates in evidence_dates.items():
        control = controls.get(control_id)
        window = core.FREQUENCY_DAYS.get(control.frequency or "") if control else None
        if not window:
            continue
        expected = max(dates) + timedelta(days=window)
        if expected <= horizon:
            dated.append({"kind": "control_cycle", "date": _iso(expected),
                          "title": f"Next evidence expected for “{control.name}”", "control_id": control_id})
    for item in dated:  # a missed date (e.g. evidence expected in May) must never read as an upcoming one
        item["overdue"] = item["date"] < today.isoformat()
    dated.sort(key=lambda i: i["date"])
    return {"items": dated, "event_driven": event_driven[:50], "horizon_days": days}


# ─── Overview ────────────────────────────────────────────────────────────────


def review_counts(db, scope: Scope) -> dict:
    queue = review_queue(db, scope, counts_only=True)
    return {group["key"]: group["count"] for group in queue["groups"]}


def overview(db, scope: Scope) -> dict:
    prepare_session(db)
    rows = requirement_rows(db, scope)
    applying = [r for r in rows if r["applicability"]["state"] in applicability.APPLYING_STATES]
    coverage = Counter(r["coverage"]["state"] for r in applying)
    gaps = [r for r in applying if r["coverage"]["state"] in ("no_control_linked", "control_confirmed_no_evidence",
                                                              "evidence_out_of_date")]
    impacts = (db.query(Impact).filter(Impact.workspace_id == scope.workspace_id, Impact.status == "open")
               .order_by(Impact.created_at.desc()).all())
    profile = core.profile(db, scope.workspace_id)
    own_docs = (db.query(GraphDocument).filter(GraphDocument.workspace_id == scope.workspace_id).all())
    roles = Counter(gd.role for gd in own_docs)
    health = Counter(gd.extraction_status for gd in own_docs)
    reviews = review_counts(db, scope)
    due = due_items(db, scope, days=30, rows=rows)
    return {
        "profile": {**profile, "labels": [taxonomy.label(c) for c in profile["category_codes"]]},
        "totals": {
            "requirements_visible": len(rows), "requirements_applying": len(applying),
            "applicability": dict(Counter(r["applicability"]["state"] for r in rows)),
            "coverage": dict(coverage),
            "awaiting_review": sum(reviews.values()),
            "needs_re_review": coverage.get("needs_re_review", 0),
            "open_changes": len(impacts),
            "due_30_days": len(due["items"]),
        },
        "coverage_labels": core.COVERAGE_LABELS,
        "reviews": reviews,
        "gaps": [{"lineage_id": r["lineage_id"], "summary": r["summary"], "quote": r["quote"],
                  "coverage": r["coverage"], "document": r["document"].get("title")} for r in gaps[:8]],
        "gap_wording": "Not established in Iroko's records. This is not a compliance finding.",
        "changes": [impact_payload(db, scope, i) for i in impacts[:5]],
        "due": due["items"][:8],
        "setup": {
            "licence_categories": bool(profile["category_codes"]) and profile["basis"] == "confirmed",
            "licence_from_filing_profile": profile["basis"] == "from_filing_profile",
            "policies_uploaded": roles.get("policy", 0) + roles.get("procedure", 0),
            "evidence_uploaded": roles.get("evidence_record", 0),
            "suggestions_to_review": sum(reviews.values()),
        },
        "extraction": {"documents": len(own_docs), "by_status": dict(health),
                       "problems": [{"document_id": gd.document_id, "title": gd.title, "status": gd.extraction_status,
                                     "error": gd.error} for gd in own_docs
                                    if gd.extraction_status in ("failed", "deferred")][:10]},
    }


# ─── Controls ────────────────────────────────────────────────────────────────


def controls_list(db, scope: Scope, include_retired: bool = False) -> list[dict]:
    prepare_session(db)
    query = db.query(Control).filter(control_visible(scope, Control))
    if not include_retired:
        query = query.filter(Control.status == "active")
    controls = query.order_by(Control.name).all()
    links = core.workspace_links(db, scope)
    people = names(db, [c.owner_user_id for c in controls] + [c.created_by for c in controls]
                   + [c.reviewed_by for c in controls])
    docs = document_info(db, scope, [c.document_id for c in controls])
    by_control = defaultdict(lambda: {"requirements_confirmed": 0, "requirements_suggested": 0,
                                      "evidence_confirmed": 0, "evidence_suggested": 0, "latest_evidence": None})
    for link in links:
        if link.review_status == "rejected":
            continue
        confirmed = link.review_status == "confirmed"
        if link.relation == "addresses" and link.from_type == "control":
            by_control[link.from_id]["requirements_confirmed" if confirmed else "requirements_suggested"] += 1
        elif link.relation == "evidences" and link.to_type == "control":
            stats = by_control[link.to_id]
            stats["evidence_confirmed" if confirmed else "evidence_suggested"] += 1
            if confirmed:
                ev = core.evidence_date(db.get(GraphDocument, link.from_id))
                if ev and (stats["latest_evidence"] is None or ev.isoformat() > stats["latest_evidence"]):
                    stats["latest_evidence"] = ev.isoformat()
    return [{
        "id": c.id, "name": c.name, "summary": c.summary, "quote": c.quote, "frequency": c.frequency,
        "evidence_expected": c.evidence_expected, "topics": c.topics or [], "status": c.status,
        "owner": {"user_id": c.owner_user_id, "name": people.get(c.owner_user_id), "team": c.owner_team},
        "performer": c.performer_span, "document": docs.get(c.document_id) if c.document_id else None,
        "page_number": c.page_number, "section": c.section_heading,
        "review": status_payload(c, people), "has_proposal": bool(c.proposal), **by_control[c.id],
    } for c in controls]


# ─── Details ─────────────────────────────────────────────────────────────────


def history(db, subject_ids, people=None, limit=50) -> list[dict]:
    ids = [i for i in set(subject_ids or ()) if i]
    if not ids:
        return []
    rows = (db.query(GraphEvent).filter(GraphEvent.subject_id.in_(ids)).order_by(GraphEvent.created_at.desc())
            .limit(limit).all())
    people = people if people is not None else names(db, [r.actor_user_id for r in rows])
    return [{"at": _iso(r.created_at), "action": r.action, "actor": people.get(r.actor_user_id) or ("Iroko" if not r.actor_user_id else "A user"),
             "from": r.from_status, "to": r.to_status, "note": r.note} for r in rows]


def link_payload(db, scope: Scope, link: Link, docs=None, people=None, detail=False, labels=None) -> dict:
    docs = docs if docs is not None else document_info(db, scope, [a.get("document_id") for a in link.anchors or []]
                                                      + [link.from_document_id, link.to_document_id])
    people = people if people is not None else names(db, [link.reviewed_by, link.created_by])
    labels = labels if labels is not None else endpoint_labels(db, scope, [link], docs)
    payload = {
        "id": link.id, "relation": link.relation, "relation_label": RELATION_LABELS.get(link.relation, link.relation),
        "layer": link.layer,
        # Named endpoints ("Monthly BVN exception reconciliation", the record's title): every panel
        # and the chat trace show what is linked, not just "control" or "document".
        "from": {"type": link.from_type, "id": link.from_id, **labels[(link.from_type, link.from_id)]},
        "to": {"type": link.to_type, "id": link.to_id, **labels[(link.to_type, link.to_id)]},
        "attributes": link.attributes or {},
        "status": status_payload(link, people), "stale_reason": link.stale_reason,
        "rationale": link.rationale, "rationale_label": "Iroko's reasoning (not a finding)" if link.rationale else None,
        "anchors": [anchor_payload(a, docs) for a in link.anchors or []],
        "has_proposal": bool(link.proposal), "can_review": False,
    }
    if detail:
        from services.compliance_graph.review import can_review

        payload["can_review"] = can_review(db, scope, link)
        payload["proposal"] = link.proposal
        payload["history"] = history(db, [link.id])
    return payload


def link_detail(db, scope: Scope, link_id: str) -> dict:
    prepare_session(db)
    link = db.query(Link).filter(Link.id == link_id, link_visible(scope, Link)).first()
    if link is None:
        raise GraphNotFound("That link is not available")
    return link_payload(db, scope, link, detail=True)


def endpoint_labels(db, scope, links, docs=None) -> dict:
    """Labels for every endpoint of these links in a few batched queries, not one lookup per link."""
    wanted = {pair for link in links for pair in ((link.from_type, link.from_id), (link.to_type, link.to_id))}
    lineages = sorted({key for kind, key in wanted if kind == "obligation"})
    obligations = core.obligations_by_lineage(db, scope, lineages) if lineages else {}
    control_ids = sorted({key for kind, key in wanted if kind == "control"})
    controls = {c.id: c for c in db.query(Control).filter(Control.id.in_(control_ids))} if control_ids else {}
    known = dict(docs or {})
    missing = sorted({key for kind, key in wanted if kind == "document" and key not in known})
    if missing:
        known.update(document_info(db, scope, missing))
    out = {}
    for kind, key in wanted:
        if kind == "obligation":
            o = obligations.get(key)
            out[(kind, key)] = {"label": (o.summary or o.quote[:120]) if o else "A requirement no longer available",
                                "available": bool(o)}
        elif kind == "control":
            c = controls.get(key)
            out[(kind, key)] = {"label": c.name if c and c.workspace_id == scope.workspace_id else "A control",
                                "available": bool(c)}
        elif kind == "document":
            info = known.get(key)
            out[(kind, key)] = {"label": info["title"] if info else "A document", "available": bool(info)}
        else:
            out[(kind, key)] = _endpoint_label(db, scope, kind, key)  # no database lookup for these kinds
    return out


def _endpoint_label(db, scope, kind, key) -> dict:
    if kind == "obligation":
        o = core.obligations_by_lineage(db, scope, [key]).get(key)
        return {"label": (o.summary or o.quote[:120]) if o else "A requirement no longer available", "available": bool(o)}
    if kind == "control":
        c = db.get(Control, key)
        return {"label": c.name if c and c.workspace_id == scope.workspace_id else "A control", "available": bool(c)}
    if kind == "document":
        info = document_info(db, scope, [key]).get(key)
        return {"label": info["title"] if info else "A document", "available": bool(info)}
    if kind == "category":
        return {"label": taxonomy.label(key), "available": True}
    if kind == "act":
        return {"label": taxonomy.act_title(key), "available": True}
    if kind == "return":
        try:
            from services.regulatory_returns.catalog import RETURNS_BY_ID

            spec = RETURNS_BY_ID.get(key)
            return {"label": spec.short_title if spec else key, "available": bool(spec)}
        except Exception:
            return {"label": key, "available": True}
    if kind == "reference":
        return {"label": f"{key} (not in your library — upload it)", "available": False}
    return {"label": key, "available": True}


def requirement_detail(db, scope: Scope, lineage_id: str) -> dict:
    prepare_session(db)
    rows = {r["lineage_id"]: r for r in requirement_rows(db, scope, lineage_ids=[lineage_id])}
    current = rows.get(lineage_id)
    versions = (db.query(Obligation).filter(Obligation.lineage_id == lineage_id,
                                            obligation_visible(scope, Obligation, current=False))
                .order_by(Obligation.created_at).all())
    if current is None and not versions:
        raise GraphNotFound("That requirement is not available")
    links = [link for link in db.query(Link).filter(
        ((Link.to_type == "obligation") & (Link.to_id == lineage_id)) | ((Link.from_type == "obligation") & (Link.from_id == lineage_id)),
        link_visible(scope, Link))]
    doc_ids = {v.document_id for v in versions} | {link.from_document_id for link in links} | {link.to_document_id for link in links}
    for link in links:
        doc_ids |= {a.get("document_id") for a in link.anchors or []}
    docs = document_info(db, scope, doc_ids)
    people = names(db, [link.reviewed_by for link in links] + [link.created_by for link in links])
    applies_links = []
    if versions:
        applies_links = db.query(Link).filter(
            Link.relation == "applies_to", Link.from_type == "document", Link.from_id == versions[-1].document_id,
            Link.status == "active").all()
    labels = endpoint_labels(db, scope, links + applies_links, docs)
    applies = [link_payload(db, scope, link, docs, people, labels=labels) for link in applies_links]
    return {
        "requirement": current or {"lineage_id": lineage_id, "quote": versions[-1].quote, "summary": versions[-1].summary,
                                   "document": docs.get(versions[-1].document_id), "unavailable": True},
        "versions": [{"id": v.id, "quote": v.quote, "document": docs.get(v.document_id), "status": v.status,
                      "page_number": v.page_number, "section": v.section_heading} for v in versions],
        "links": [link_payload(db, scope, link, docs, people, labels=labels) for link in links],
        "addressees": applies,
        "history": history(db, [v.id for v in versions] + [lineage_id]),
        "can_decide": is_workspace_admin(scope, scope.workspace_id),
    }


def control_detail(db, scope: Scope, control_id: str) -> dict:
    prepare_session(db)
    c = db.query(Control).filter(Control.id == control_id, control_visible(scope, Control)).first()
    if c is None:
        raise GraphNotFound("That control is not available")
    links = db.query(Link).filter(((Link.from_type == "control") & (Link.from_id == c.id))
                                  | ((Link.to_type == "control") & (Link.to_id == c.id)),
                                  link_visible(scope, Link)).all()
    doc_ids = {c.document_id} | {link.from_document_id for link in links} | {link.to_document_id for link in links}
    docs = document_info(db, scope, doc_ids)
    people = names(db, [c.owner_user_id, c.created_by, c.reviewed_by] + [link.reviewed_by for link in links])
    item = next((x for x in controls_list(db, scope, include_retired=True) if x["id"] == c.id), None)
    labels = endpoint_labels(db, scope, links, docs)
    return {"control": item, "anchor_history": c.anchor_history or [], "proposal": c.proposal,
            "links": [link_payload(db, scope, link, docs, people, labels=labels) for link in links],
            "history": history(db, [c.id], people),
            "can_review": is_workspace_admin(scope, c.workspace_id)}


def document_detail(db, scope: Scope, document_id: str) -> dict:
    prepare_session(db)
    if not is_document_visible(db, scope, document_id, current=False):
        raise GraphNotFound("That document is not available")
    info = document_info(db, scope, [document_id]).get(document_id)
    gd = db.get(GraphDocument, document_id)
    links = db.query(Link).filter(((Link.from_type == "document") & (Link.from_id == document_id))
                                  | ((Link.to_type == "document") & (Link.to_id == document_id)),
                                  link_visible(scope, Link)).all()
    docs = document_info(db, scope, {document_id} | {link.from_document_id for link in links}
                         | {link.to_document_id for link in links})
    people = names(db, [link.reviewed_by for link in links])
    requirements = db.query(Obligation).filter(Obligation.document_id == document_id, Obligation.status == "active").count()
    return {"document": info, "facts": (gd.facts if gd else {}) or {},
            "effective_anchor": gd.effective_anchor if gd else None,
            "requirements": requirements,
            "links": [link_payload(db, scope, link, docs, people, labels=endpoint_labels(db, scope, links, docs))
                      for link in links],
            "history": history(db, [document_id])}


# ─── Explorer ────────────────────────────────────────────────────────────────

LANES = {"instrument": 0, "reference": 0, "act": 0, "requirement": 1, "control": 2, "evidence": 3}
MAX_NODES = 80


def neighbourhood(db, scope: Scope, kind: str, key: str, depth: int = 1, include_suggested: bool = True) -> dict:
    """A bounded, permission-checked subgraph laid out in lanes (instrument → requirement → control → evidence)."""
    prepare_session(db)
    depth = max(1, min(int(depth or 1), 2))
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    links = [link for link in db.query(Link).filter(link_visible(scope, Link))
             if link.review_status != "rejected" and (include_suggested or link.review_status in ("confirmed", "needs_re_review")
                                                       or link.basis == "stated")
             and link.relation not in ("applies_to", "filed_via")]
    obligations = {o.lineage_id: o for o in core.visible_obligations(db, scope, current=True)}
    controls = {c.id: c for c in core.active_controls(db, scope)}

    def node_id(t, k):
        return f"{t}:{k}"

    def add_node(t, k):
        nid = node_id(t, k)
        if nid in nodes or len(nodes) >= MAX_NODES:
            return nid in nodes
        if t == "requirement":
            o = obligations.get(k)
            if o is None:
                return False
            nodes[nid] = {"id": nid, "type": t, "key": k, "label": o.summary or o.quote[:110], "lane": LANES[t],
                          "document_id": o.document_id}
        elif t == "control":
            c = controls.get(k)
            if c is None:
                return False
            nodes[nid] = {"id": nid, "type": t, "key": k, "label": c.name, "lane": LANES[t],
                          "status": c.review_status}
        elif t in ("instrument", "evidence"):
            info = document_info(db, scope, [k]).get(k)
            if info is None:
                return False
            nodes[nid] = {"id": nid, "type": t, "key": k, "label": info["title"], "lane": LANES[t],
                          "sublabel": info.get("reference") or info.get("regulator"), "status": info.get("status"),
                          "awaiting_publication": info.get("awaiting_publication")}
        elif t == "act":
            nodes[nid] = {"id": nid, "type": t, "key": k, "label": taxonomy.act_title(k), "lane": LANES[t]}
        elif t == "reference":
            nodes[nid] = {"id": nid, "type": t, "key": k, "label": f"{k} (not in your library)", "lane": LANES[t]}
        else:
            return False
        return True

    def endpoint(t, k):
        if t == "obligation":
            return "requirement", k
        if t == "document":
            gd = db.get(GraphDocument, k)
            return ("evidence" if gd is not None and gd.role == "evidence_record" else "instrument"), k
        return t, k

    def add_edge(link):
        ft, fk = endpoint(link.from_type, link.from_id)
        tt, tk = endpoint(link.to_type, link.to_id)
        if node_id(ft, fk) not in nodes or node_id(tt, tk) not in nodes:
            return
        style = ("re_review" if link.review_status == "needs_re_review" else
                 "confirmed" if link.review_status == "confirmed" else
                 "stated" if link.basis == "stated" else "suggested")
        edges[link.id] = {"id": link.id, "from": node_id(ft, fk), "to": node_id(tt, tk), "relation": link.relation,
                          "label": RELATION_LABELS.get(link.relation, link.relation), "style": style,
                          "basis": link.basis, "review_status": link.review_status}

    start_type = {"obligation": "requirement", "requirement": "requirement", "document": "instrument"}.get(kind, kind)
    if start_type == "instrument":
        gd = db.get(GraphDocument, key)
        if gd is not None and gd.role == "evidence_record":
            start_type = "evidence"
    if not add_node(start_type, key):
        raise GraphNotFound("That item is not available")
    frontier = {node_id(start_type, key)}
    for _ in range(depth):
        next_frontier = set()
        for nid in list(frontier):
            n = nodes.get(nid)
            if n is None:
                continue
            # Requirements belong to their instrument; instruments contain their requirements.
            if n["type"] == "requirement":
                parent = node_id("instrument", n["document_id"])
                if add_node("instrument", n["document_id"]):
                    edges[f"contains:{n['key']}"] = {"id": f"contains:{n['key']}", "from": parent, "to": nid,
                                                     "relation": "contains", "label": "contains", "style": "contains"}
                    next_frontier.add(parent)
            if n["type"] == "instrument":
                for o in [o for o in obligations.values() if o.document_id == n["key"]][:25]:
                    if add_node("requirement", o.lineage_id):
                        edges[f"contains:{o.lineage_id}"] = {"id": f"contains:{o.lineage_id}", "from": nid,
                                                             "to": node_id("requirement", o.lineage_id),
                                                             "relation": "contains", "label": "contains", "style": "contains"}
                        next_frontier.add(node_id("requirement", o.lineage_id))
            for link in links:
                ends = [endpoint(link.from_type, link.from_id), endpoint(link.to_type, link.to_id)]
                ids = [node_id(t, k) for t, k in ends]
                if nid not in ids:
                    continue
                other_type, other_key = ends[1] if ids[0] == nid else ends[0]
                if add_node(other_type, other_key):
                    next_frontier.add(node_id(other_type, other_key))
        frontier = next_frontier
    for link in links:
        add_edge(link)
    return {"focus": node_id(start_type, key), "nodes": list(nodes.values()), "edges": list(edges.values()),
            "truncated": len(nodes) >= MAX_NODES,
            "lanes": ["Instruments", "Requirements", "Your controls", "Your evidence"]}


# ─── Review queue ────────────────────────────────────────────────────────────


def review_queue(db, scope: Scope, kind: str | None = None, limit: int = 100, counts_only: bool = False) -> dict:
    """Everything the caller may decide on, grouped. Items carry both sides' words.

    counts_only: the same filtering without building payloads (the Overview's tiles).
    """
    prepare_session(db)
    groups: dict[str, list] = defaultdict(list)
    links = db.query(Link).filter(link_visible(scope, Link), Link.status == "active",
                                  Link.review_status.in_(("proposed", "needs_re_review"))).all()
    doc_ids = set()
    for link in links:
        doc_ids |= {link.from_document_id, link.to_document_id} | {a.get("document_id") for a in link.anchors or []}
    docs = document_info(db, scope, doc_ids)
    people = {} if counts_only else names(db, [link.created_by for link in links])
    from services.compliance_graph.review import can_review

    chosen: list[tuple[str, Link]] = []
    for link in links:
        if link.layer == "library":
            if link.basis == "stated" and link.relation in ("references", "issued_under"):
                continue  # plain citations are facts; they need no decision
            if not can_review(db, scope, link):
                continue
            key = "applicability" if link.relation == "applies_to" else "regulation_facts"
        else:
            if not is_workspace_admin(scope, link.workspace_id):
                continue
            key = "control_mappings" if link.relation == "addresses" else "evidence_links"
        chosen.append((key, link))
    labels = {} if counts_only else endpoint_labels(db, scope, [link for _key, link in chosen], docs)
    for key, link in chosen:
        if counts_only:
            groups[key].append(link.id)
            continue
        payload = link_payload(db, scope, link, docs, people, labels=labels)
        payload["can_review"] = True
        groups[key].append(payload)

    if is_workspace_admin(scope, scope.workspace_id):
        for c in db.query(Control).filter(control_visible(scope, Control), Control.status == "active",
                                          Control.review_status.in_(("proposed", "needs_re_review"))):
            groups["controls"].append({"id": c.id, "name": c.name, "summary": c.summary, "quote": c.quote,
                                       "performer": c.performer_span, "frequency": c.frequency,
                                       "status": status_payload(c, {}), "document": docs.get(c.document_id)})

    graph_docs = db.query(GraphDocument).filter(
        document_visible(scope, GraphDocument.document_id, current=True),
        (GraphDocument.role_suggestion.isnot(None)) | (GraphDocument.role_basis == "suggested")
        | (GraphDocument.effective_basis == "suggested")).all()
    for gd in graph_docs:
        try:
            reviewer = can_review_library(db, scope, [gd.document_id])
        except Exception:
            reviewer = False
        info = document_info(db, scope, [gd.document_id]).get(gd.document_id)
        if (gd.role_suggestion or gd.role_basis == "suggested") and (reviewer or (
                info and not info["shared"] and is_workspace_admin(scope, gd.workspace_id))):
            groups["document_roles"].append({"document": info, "role": gd.role, "role_basis": gd.role_basis,
                                             "suggestion": gd.role_suggestion or gd.role})
        if gd.effective_basis == "suggested" and reviewer:
            groups["effective_dates"].append({"document": info, "effective_date": _iso(gd.effective_date),
                                              "anchor": gd.effective_anchor})

    if scope.is_superadmin:
        from services.compliance_graph.sync import _newer_unshared

        for access in db.query(DocumentAccess).filter(DocumentAccess.shared_regulatory.is_(True)):
            doc = db.get(Document, access.document_id)
            if doc is None or doc.status != "superseded":
                continue
            newer = _newer_unshared(db, access.document_id)
            if newer:
                groups["share_new_version"].append({"document": document_info(db, scope, [access.document_id]).get(access.document_id),
                                                    "new_document": {"id": newer, "title": db.get(Document, newer).title}})

    titles = {
        "regulation_facts": "Relationships between instruments",
        "applicability": "Who requirements are addressed to",
        "control_mappings": "Your controls and requirements",
        "evidence_links": "Your evidence",
        "controls": "Controls found in your policies",
        "document_roles": "Document roles",
        "effective_dates": "Effective dates",
        "share_new_version": "Newer versions waiting to be shared",
    }
    order = ["control_mappings", "evidence_links", "controls", "document_roles", "regulation_facts", "applicability",
             "effective_dates", "share_new_version"]
    out = []
    for key in order:
        if kind and key != kind:
            continue
        items = groups.get(key, [])
        out.append({"key": key, "title": titles[key], "count": len(items), "items": items[:limit]})
    return {"groups": out}


# ─── Changes ─────────────────────────────────────────────────────────────────


def impact_payload(db, scope: Scope, impact: Impact) -> dict:
    event = db.get(ChangeEvent, impact.event_id) if impact.event_id else None
    affected = impact.affected or {}
    links = [db.get(Link, lid) for lid in affected.get("links", [])]
    links = [link for link in links if link is not None and link.workspace_id == scope.workspace_id]
    controls = [db.get(Control, cid) for cid in affected.get("controls", [])]
    details = (event.details or {}) if event else {}
    changed_quotes = {item["lineage_id"]: item for item in details.get("modified", [])}
    removed_quotes = {item["lineage_id"]: item for item in details.get("removed", [])}
    return {
        "id": impact.id, "kind": impact.kind, "summary": impact.summary, "status": impact.status,
        "created_at": _iso(impact.created_at), "acknowledged_at": _iso(impact.acknowledged_at),
        "flagged": len(affected.get("flagged", [])),
        "links": [{"id": link.id, "relation": link.relation, "status": link.review_status,
                   "stale_reason": link.stale_reason} for link in links],
        "controls": [{"id": c.id, "name": c.name, "owner_user_id": c.owner_user_id, "owner_team": c.owner_team}
                     for c in controls if c is not None and c.workspace_id == scope.workspace_id],
        "changes": [{"lineage_id": lid, "old_quote": changed_quotes.get(lid, removed_quotes.get(lid, {})).get("old_quote")
                     or removed_quotes.get(lid, {}).get("quote"),
                     "new_quote": changed_quotes.get(lid, {}).get("new_quote"),
                     "removed": lid in removed_quotes} for lid in affected.get("lineages", [])
                    if lid in changed_quotes or lid in removed_quotes],
        "trigger_document": document_info(db, scope, [event.trigger_document_id]).get(event.trigger_document_id) if event else None,
        "subject_document": document_info(db, scope, [event.subject_document_id]).get(event.subject_document_id) if event else None,
    }


def impacts(db, scope: Scope, status: str | None = None) -> list[dict]:
    prepare_session(db)
    query = db.query(Impact).filter(Impact.workspace_id == scope.workspace_id)
    if status:
        query = query.filter(Impact.status == status)
    return [impact_payload(db, scope, i) for i in query.order_by(Impact.created_at.desc()).limit(200)]


# ─── Search, people, admin ───────────────────────────────────────────────────


def search(db, scope: Scope, q: str, limit: int = 12) -> dict:
    prepare_session(db)
    q = (q or "").strip()
    if len(q) < 2:
        return {"instruments": [], "requirements": [], "controls": [], "evidence": []}
    like = f"%{q.lower()}%"
    from sqlalchemy import func

    docs = (db.query(GraphDocument)
            .filter(document_visible(scope, GraphDocument.document_id, current=True),
                    (func.lower(GraphDocument.title).like(like)) | (func.lower(GraphDocument.reference_number).like(like)))
            .limit(limit * 2).all())
    instruments = [{"id": d.document_id, "title": d.title, "reference": d.reference_number, "role": d.role}
                   for d in docs if d.role != "evidence_record"][:limit]
    evidence = [{"id": d.document_id, "title": d.title} for d in docs if d.role == "evidence_record"][:limit]
    reqs = (db.query(Obligation).filter(obligation_visible(scope, Obligation, current=True),
                                        (func.lower(Obligation.quote).like(like)) | (func.lower(Obligation.summary).like(like)))
            .limit(limit).all())
    controls = (db.query(Control).filter(control_visible(scope, Control), Control.status == "active",
                                         (func.lower(Control.name).like(like)) | (func.lower(Control.summary).like(like)))
                .limit(limit).all())
    return {"instruments": instruments,
            "requirements": [{"lineage_id": o.lineage_id, "summary": o.summary, "quote": o.quote} for o in reqs],
            "controls": [{"id": c.id, "name": c.name} for c in controls], "evidence": evidence}


def people(db, scope: Scope) -> list[dict]:
    prepare_session(db)
    ids = [row[0] for row in db.query(Membership.user_id).filter(Membership.workspace_id == scope.workspace_id)]
    if scope.workspace_id.startswith("user:"):
        ids.append(scope.workspace_id.split(":", 1)[1])
    users = db.query(User).filter(User.id.in_(set(ids) or {""}), User.is_active.is_(True)).all()
    return [{"id": u.id, "name": u.full_name or u.email, "email": u.email, "role": u.role} for u in users]


def admin_runs(db, scope: Scope) -> dict:
    """Extraction health. Other workspaces' private documents appear as counts only."""
    prepare_session(db)
    rows = db.query(GraphDocument).all()
    visible, private = [], Counter()
    for gd in rows:
        access = db.get(DocumentAccess, gd.document_id)
        if access is not None and (access.shared_regulatory or access.workspace_id == scope.workspace_id):
            visible.append(gd)
        else:
            private[gd.extraction_status] += 1
    recent = (db.query(GraphRun).filter(GraphRun.target_id.in_([gd.document_id for gd in visible] or [""]))
              .order_by(GraphRun.started_at.desc()).limit(50).all())
    return {
        "documents": [{"id": gd.document_id, "title": gd.title, "role": gd.role, "status": gd.extraction_status,
                       "error": gd.error, "prompt_version": gd.prompt_version} for gd in visible],
        "other_workspaces": dict(private),
        "runs": [{"target_id": r.target_id, "stage": r.stage, "status": r.status, "model": r.model,
                  "tokens_estimated": r.tokens_estimated, "at": _iso(r.started_at)} for r in recent],
    }
