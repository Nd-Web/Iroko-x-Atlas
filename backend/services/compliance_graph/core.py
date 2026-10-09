"""
Shared reads: what a workspace can see, what applies to it, how covered it is.

Everything starts from visibility.py's SQL predicates, so the sets below never
contain a row the workspace may not open. Applicability and coverage are
computed here, on demand, from stored facts and explicit decisions; they are
never stored as verdicts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import or_

from ingestion.db import prepare_session
from models.compliance_graph import (Control, GraphDocument, InstitutionProfile, Link, Obligation,
                                     ObligationStatus)
from models.database import Document
from services.compliance_graph import applicability, taxonomy
from services.compliance_graph.visibility import (Scope, control_visible, document_visible, link_visible,
                                                  obligation_visible)

WORKSPACE_RELATIONS = ("addresses", "evidences")
FREQUENCY_DAYS = {"daily": 2, "weekly": 9, "monthly": 35, "quarterly": 100, "semiannual": 190, "annual": 380}


def profile(db, workspace_id: str) -> dict:
    """The workspace's licence categories; defaults to the returns module's filing profile."""
    row = db.get(InstitutionProfile, workspace_id)
    if row is not None:
        return {"category_codes": taxonomy.valid_codes(row.category_codes), "basis": row.basis,
                "updated_by": row.updated_by, "updated_at": row.updated_at.isoformat() if row.updated_at else None}
    try:
        from models.filing import FilingProfile

        filing = db.get(FilingProfile, workspace_id)
    except Exception:
        filing = None
    category = (filing.profile or {}).get("licence_category") if filing is not None else None
    if category in taxonomy.CATEGORIES:
        return {"category_codes": [category], "basis": "from_filing_profile", "updated_by": None, "updated_at": None}
    return {"category_codes": [], "basis": None, "updated_by": None, "updated_at": None}


def visible_obligations(db, scope: Scope, *, current: bool = True, document_ids=None,
                        lineage_ids=None) -> list[Obligation]:
    prepare_session(db)
    query = db.query(Obligation).filter(obligation_visible(scope, Obligation, current=current))
    if document_ids is not None:
        query = query.filter(Obligation.document_id.in_(list(document_ids)))
    if lineage_ids is not None:
        query = query.filter(Obligation.lineage_id.in_(list(lineage_ids)))
    return query.order_by(Obligation.document_id, Obligation.position).all()


def addressee_links(db, document_ids) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = defaultdict(list)
    ids = list(set(document_ids or ()))
    if not ids:
        return out
    rows = db.query(Link).filter(Link.relation == "applies_to", Link.from_type == "document",
                                 Link.from_id.in_(ids), Link.status == "active",
                                 Link.review_status != "rejected").all()
    for row in rows:
        out[row.from_id].append(([row.to_id], row.basis, row.review_status))
    return out


def decisions(db, workspace_id: str, lineage_ids=None) -> dict[str, ObligationStatus]:
    query = db.query(ObligationStatus).filter(ObligationStatus.workspace_id == workspace_id)
    if lineage_ids is not None:
        ids = list(set(lineage_ids))
        if not ids:
            return {}
        query = query.filter(ObligationStatus.lineage_id.in_(ids))
    return {row.lineage_id: row for row in query}


def applicability_of(db, scope: Scope, obligations, codes=None) -> dict[str, str]:
    """lineage_id -> applicability state (applicability.LABELS keys)."""
    codes = profile(db, scope.workspace_id)["category_codes"] if codes is None else codes
    by_doc = addressee_links(db, [o.document_id for o in obligations])
    made = decisions(db, scope.workspace_id, [o.lineage_id for o in obligations])
    out = {}
    for o in obligations:
        decision = made.get(o.lineage_id)
        out[o.lineage_id] = applicability.evaluate(
            codes, o.addressee_codes, o.addressee_basis, by_doc.get(o.document_id, []),
            decision.applicability_decision if decision else None)
    return out


def workspace_links(db, scope: Scope, relations=WORKSPACE_RELATIONS) -> list[Link]:
    prepare_session(db)
    return (db.query(Link)
            .filter(Link.workspace_id == scope.workspace_id, Link.relation.in_(relations), link_visible(scope, Link))
            .all())


def active_controls(db, scope: Scope) -> list[Control]:
    prepare_session(db)
    return (db.query(Control)
            .filter(Control.status == "active", control_visible(scope, Control))
            .order_by(Control.name).all())


def evidence_documents(db, scope: Scope) -> list[GraphDocument]:
    prepare_session(db)
    return (db.query(GraphDocument)
            .filter(GraphDocument.role == "evidence_record",
                    document_visible(scope, GraphDocument.document_id, current=True))
            .all())


def evidence_date(gd: GraphDocument | None) -> date | None:
    from services.compliance_graph.common import parse_iso_date

    facts = ((gd.facts or {}).get("evidence") or {}) if gd else {}
    return parse_iso_date(facts.get("period_end")) or parse_iso_date(facts.get("record_date"))


@dataclass
class Coverage:
    state: str
    partial: bool = False
    controls_confirmed: list = field(default_factory=list)
    controls_suggested: list = field(default_factory=list)
    evidence_confirmed: list = field(default_factory=list)
    evidence_suggested: list = field(default_factory=list)
    re_review: list = field(default_factory=list)
    latest_evidence: date | None = None


COVERAGE_LABELS = {
    "not_applicable": "Not applicable",
    "no_control_linked": "No control linked — not established in Iroko's records",
    "control_suggested": "Control suggested — awaiting review",
    "control_confirmed_no_evidence": "Control confirmed — no evidence in Iroko's records",
    "evidence_suggested": "Evidence suggested — awaiting review",
    "evidence_on_record": "Evidence on record",
    "evidence_out_of_date": "Evidence on record is older than the control's cycle",
    "needs_re_review": "Needs re-review",
}


def coverage_of(db, scope: Scope, lineage_ids, applicable: dict[str, str], *, today: date | None = None,
                links=None, controls=None) -> dict[str, Coverage]:
    """lineage_id -> Coverage, from the workspace's own confirmed and suggested links."""
    from services.compliance_graph.common import lagos_today

    today = today or lagos_today()
    links = workspace_links(db, scope) if links is None else links
    controls = {c.id: c for c in (active_controls(db, scope) if controls is None else controls)}
    addresses = defaultdict(list)
    evidence_of_control = defaultdict(list)
    evidence_of_lineage = defaultdict(list)
    for link in links:
        if link.review_status == "rejected":
            continue
        if link.relation == "addresses" and link.to_type == "obligation" and link.from_id in controls:
            addresses[link.to_id].append(link)
        elif link.relation == "evidences":
            if link.to_type == "control":
                evidence_of_control[link.to_id].append(link)
            elif link.to_type == "obligation":
                evidence_of_lineage[link.to_id].append(link)
    evidence_docs = {gd.document_id: gd for gd in db.query(GraphDocument).filter(
        GraphDocument.document_id.in_({link.from_id for link in links if link.relation == "evidences"} or {""}))}
    out = {}
    for lineage in lineage_ids:
        if applicable.get(lineage) in ("not_applicable", "not_addressed"):
            out[lineage] = Coverage("not_applicable")
            continue
        cov = Coverage("no_control_linked")
        chain = list(addresses.get(lineage, []))
        evidence = list(evidence_of_lineage.get(lineage, []))
        for link in chain:
            (cov.controls_confirmed if link.review_status == "confirmed" else cov.controls_suggested).append(link)
            if link.review_status == "needs_re_review":
                cov.re_review.append(link)
            if (link.attributes or {}).get("coverage") == "partial":
                cov.partial = True
            if link.review_status == "confirmed":
                evidence.extend(evidence_of_control.get(link.from_id, []))
        frequencies = [controls[link.from_id].frequency for link in cov.controls_confirmed
                       if link.from_id in controls and controls[link.from_id].frequency]
        for link in evidence:
            if link.review_status == "needs_re_review":
                cov.re_review.append(link)
            (cov.evidence_confirmed if link.review_status == "confirmed" else cov.evidence_suggested).append(link)
        dates = [evidence_date(evidence_docs.get(link.from_id)) for link in cov.evidence_confirmed]
        dates = [d for d in dates if d]
        cov.latest_evidence = max(dates) if dates else None
        if cov.re_review:
            cov.state = "needs_re_review"
        elif cov.evidence_confirmed:
            window = min((FREQUENCY_DAYS.get(f, 0) for f in frequencies if FREQUENCY_DAYS.get(f)), default=0)
            stale = bool(window and cov.latest_evidence and cov.latest_evidence < today - timedelta(days=window))
            cov.state = "evidence_out_of_date" if stale else "evidence_on_record"
        elif cov.evidence_suggested:
            cov.state = "evidence_suggested"
        elif cov.controls_confirmed:
            cov.state = "control_confirmed_no_evidence"
        elif cov.controls_suggested:
            cov.state = "control_suggested"
        out[lineage] = cov
    return out


def document_titles(db, ids) -> dict[str, str]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    return {row.id: row.title for row in db.query(Document.id, Document.title).filter(Document.id.in_(ids))}


def obligations_by_lineage(db, scope: Scope, lineage_ids) -> dict[str, Obligation]:
    """The version of each lineage that is current for this workspace (else the latest visible)."""
    ids = list(set(lineage_ids or ()))
    if not ids:
        return {}
    current = (db.query(Obligation)
               .filter(Obligation.lineage_id.in_(ids), obligation_visible(scope, Obligation, current=True)).all())
    out = {o.lineage_id: o for o in current}
    missing = [i for i in ids if i not in out]
    if missing:
        older = (db.query(Obligation)
                 .filter(Obligation.lineage_id.in_(missing),
                         or_(Obligation.status == "active", Obligation.status == "withdrawn"),
                         document_visible(scope, Obligation.document_id, current=False))
                 .order_by(Obligation.created_at.desc()).all())
        for o in older:
            out.setdefault(o.lineage_id, o)
    return out
