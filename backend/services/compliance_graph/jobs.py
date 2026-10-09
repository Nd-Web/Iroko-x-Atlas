"""
Background graph jobs, run by the ingestion worker (python -m ingestion worker).

  graph:{document_id}   Facts about one document: its role; for a regulation
                        its addressees, requirements, relationships and
                        effective date; for a policy or procedure its controls;
                        for an evidence record what it shows. No per-workspace
                        work happens here.
  graph_ws:{workspace}  The workspace's own graph (sync.py): suggestions that
                        link its controls and evidence to requirements, the
                        impact of changes on its records, review tasks.

Jobs are time-boxed (GRAPH_JOB_TIME_BOX_SECONDS, default 150): long documents
checkpoint and continue in a new claim without spending a retry attempt.
Budget limits and model outages defer the job instead of failing it. Every
stage commits before it calls a model, so no row lock is ever held across a
remote call.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import timedelta

from ingestion.db import prepare_session
from ingestion.models import Chunk, DocumentAccess, Page, Revision
from ingestion.queue import defer, enqueue, finish, owned
from models.compliance_graph import ChangeEvent, Control, GraphDocument, GraphRun, Link, Obligation
from models.database import Document, generate_id
from services.compliance_graph import common, store
from services.compliance_graph.budget import BudgetExhausted
from services.compliance_graph.llm import ModelUnavailable, model_name

logger = logging.getLogger(__name__)

REQUIREMENT_BATCH = 30
CONTROL_BATCH = 30
MAX_CANDIDATES = 400
OUTAGE_LIMIT = timedelta(hours=24)


class Yield(Exception):
    """The claim's time box is used up; the job continues in a new claim."""


class PermanentGraphError(Exception):
    permanent = True


def time_box_seconds() -> int:
    try:
        return max(20, int(os.getenv("GRAPH_JOB_TIME_BOX_SECONDS", "150")))
    except ValueError:
        return 150


def schema_ready(db) -> bool:
    from sqlalchemy import inspect

    try:
        return inspect(db.get_bind()).has_table("cg_documents")
    except Exception:
        return False


def versions_signature() -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(common.PROMPT_VERSIONS.items()))


class Context:
    def __init__(self, db, *, complete=None, seconds=None):
        self.db = db
        self.complete = complete
        self.deadline = time.monotonic() + (seconds or time_box_seconds())
        self.usage: dict = {}

    def check_time(self):
        if time.monotonic() > self.deadline:
            raise Yield()


# ─── Entry point ─────────────────────────────────────────────────────────────


async def run_job(db, key, token, kind, target, *, complete=None, seconds=None):
    owned(db, key, token)
    prepare_session(db)
    if not common.enabled():
        defer(db, key, token, common.utcnow() + timedelta(minutes=10),
              "The compliance graph is disabled in this worker (COMPLIANCE_GRAPH_ENABLED)")
        return
    if not schema_ready(db):
        defer(db, key, token, common.utcnow() + timedelta(minutes=10),
              "Compliance graph tables are not created yet; start the API once to create them")
        return
    ctx = Context(db, complete=complete, seconds=seconds)
    try:
        if kind == "graph":
            await document_job(ctx, key, token, target)
        else:
            from services.compliance_graph.sync import workspace_job

            await workspace_job(ctx, key, token, target)
    except Yield:
        db.commit()
        defer(db, key, token, common.utcnow(), "Continuing a long document in the next slice")
    except BudgetExhausted as exc:
        db.rollback()
        _mark(db, kind, target, "deferred", str(exc))
        defer(db, key, token, exc.until, str(exc))
    except ModelUnavailable as exc:
        db.rollback()
        _outage(db, key, token, kind, target, exc)


def _mark(db, kind, target, status, error=None):
    if kind != "graph":
        return
    gd = db.get(GraphDocument, target)
    if gd is not None:
        gd.extraction_status = status
        gd.error = (error or "")[:500] or None
        db.commit()


def _outage(db, key, token, kind, target, exc):
    """Defer through a model outage for up to 24 hours (one clock per job), then fail visibly."""
    from datetime import datetime

    from models.compliance_graph import WorkspaceSync

    now = common.utcnow()
    message = f"Language model unavailable: {exc}"[:500]
    since = None
    if kind == "graph":
        holder = db.get(GraphDocument, target)
        if holder is not None:
            state = dict(holder.stage_state or {})
            if state.get("outage_since"):
                since = datetime.fromisoformat(state["outage_since"])
            else:
                state["outage_since"] = now.isoformat()
                holder.stage_state = state
            holder.extraction_status = "deferred"
            holder.error = message
    else:
        holder = db.get(WorkspaceSync, target)
        if holder is None:
            holder = WorkspaceSync(workspace_id=target)
            db.add(holder)
        since = holder.outage_since
        if since is None:
            holder.outage_since = now
        holder.last_error = message
    db.commit()
    if since is not None and now - since > OUTAGE_LIMIT:
        if kind == "graph" and holder is not None:
            holder.extraction_status = "failed"
            db.commit()
        finish(db, key, token, error=f"Language model unavailable for over 24 hours: {exc}"[:300], permanent=True)
        return
    defer(db, key, token, now + timedelta(minutes=15), message[:300])


# ─── Document job ────────────────────────────────────────────────────────────


def ensure_document(db, doc, rev, access) -> GraphDocument:
    from services.compliance_graph.extract import ROLES
    from services.compliance_graph.segment import normalize_reference

    gd = db.get(GraphDocument, doc.id)
    if gd is None:
        gd = GraphDocument(document_id=doc.id, stage_state={}, facts={}, extraction_status="pending",
                           role="other", role_basis="suggested")
        db.add(gd)
    provenance = rev.provenance or {}
    gd.workspace_id = access.workspace_id if access else None
    gd.title = doc.title
    gd.regulator = provenance.get("regulator") or gd.regulator
    gd.reference_number = (normalize_reference(provenance.get("reference_number_normalized"))
                           or normalize_reference(provenance.get("reference_number")) or gd.reference_number)
    gd.published_date = common.parse_iso_date(provenance.get("published_date"))
    gd.lineage_key = rev.source_key
    gd.previous_document_id = rev.previous_id
    if gd.role_basis != "confirmed":
        uploader_role = provenance.get("document_role")
        if uploader_role in ROLES:
            gd.role, gd.role_basis = uploader_role, "uploader"
        elif provenance.get("regulator"):
            gd.role, gd.role_basis = "regulation", "stated"
    return gd


def _load(db, document_id):
    pages = db.query(Page).filter_by(document_id=document_id).order_by(Page.position).all()
    chunks = db.query(Chunk).filter_by(document_id=document_id).order_by(Chunk.chunk_index).all()
    return pages, chunks


def _anchor(document_id, sentence, side="source", **extra) -> dict:
    return {
        "document_id": document_id, "page_number": sentence.page_number, "page_position": sentence.page_position,
        "locator": sentence.locator, "start": sentence.start, "end": sentence.end, "chunk_id": sentence.chunk_id,
        "quote": sentence.quote, "section": sentence.section_heading, "side": side, **extra,
    }


def _save_state(ctx, done_stage=None):
    state = dict(ctx.state)
    if done_stage:
        state["done"] = sorted(set(state.get("done", [])) | {done_stage})
    ctx.state = state
    ctx.gd.stage_state = state
    ctx.db.commit()


def _run_log(ctx, stage, status, counts=None, error=None):
    ctx.db.add(GraphRun(
        id=generate_id(), scope="document", target_id=ctx.doc.id, workspace_id=ctx.gd.workspace_id, stage=stage,
        status=status, model=model_name(), prompt_version=common.PROMPT_VERSIONS.get(stage),
        tokens_estimated=ctx.usage.get("tokens", 0), counts=dict(counts or {}), error=error,
        started_at=common.utcnow(), finished_at=common.utcnow(),
    ))


async def document_job(ctx, key, token, document_id):
    db = ctx.db
    doc, rev = db.get(Document, document_id), db.get(Revision, document_id)
    access = db.get(DocumentAccess, document_id)
    if not doc or not rev or not access or doc.status != "indexed" or not rev.is_current:
        gd = db.get(GraphDocument, document_id)
        if gd is not None and doc is not None and doc.status in {"archived", "rejected", "superseded"}:
            gd.extraction_status = "retired"
            db.commit()
        finish(db, key, token, state="cancelled")
        return
    gd = ensure_document(db, doc, rev, access)
    state = dict(gd.stage_state or {})
    signature = versions_signature()
    if state.get("signature") != signature or state.get("role") != gd.role:
        state = {"signature": signature, "role": gd.role, "run_id": generate_id(), "done": [],
                 **({"outage_since": state["outage_since"]} if state.get("outage_since") else {})}
    gd.stage_state = state
    gd.extraction_status = "running"
    gd.error = None
    db.commit()

    from services.compliance_graph.segment import segment, tag

    pages, chunks = _load(db, document_id)
    ctx.doc, ctx.rev, ctx.access, ctx.gd, ctx.pages, ctx.state = doc, rev, access, gd, pages, state
    ctx.sentences = tag(segment(pages, chunks))
    ctx.run_id = state["run_id"]

    stages = [("role", stage_role)]
    for name, fn in stages:
        if name not in ctx.state.get("done", []):
            await fn(ctx)
            _save_state(ctx, name)
    role = ctx.gd.role
    if role == "regulation":
        stages = [("addressees", stage_addressees), ("reference", stage_reference),
                  ("requirements", stage_requirements), ("lineage", stage_lineage),
                  ("relations", stage_relations), ("effective", stage_effective)]
    elif role in {"policy", "procedure"}:
        stages = [("controls", stage_controls), ("control_lineage", stage_control_lineage)]
    elif role == "evidence_record":
        stages = [("evidence", stage_evidence)]
    else:
        stages = []
    for name, fn in stages:
        if name in ctx.state.get("done", []):
            continue
        ctx.check_time()
        await fn(ctx)
        _save_state(ctx, name)

    gd = ctx.gd
    gd.extraction_status = "done"
    gd.prompt_version = signature
    gd.error = None
    gd.stage_state = {k: v for k, v in ctx.state.items() if k != "outage_since"}
    _run_log(ctx, "document", "done", {"role": role, "model_calls": ctx.usage.get("calls", 0)})
    db.commit()
    from services.compliance_graph.triggers import after_document_change

    after_document_change(db, document_id)
    db.commit()
    finish(db, key, token)
    db.refresh(gd)
    if gd.rerun_requested:
        gd.rerun_requested = False
        gd.stage_state = {}
        enqueue(db, "graph", document_id)
        db.commit()


# ─── Stages ──────────────────────────────────────────────────────────────────


async def stage_role(ctx):
    """The uploader's choice and regulator provenance are kept; otherwise Iroko suggests one."""
    from services.compliance_graph.extract import role_hint, suggest_role

    gd = ctx.gd
    if gd.role_basis in {"confirmed", "stated"}:
        return
    opening = "\n".join((p.text or "") for p in ctx.pages[:2])[:3000]
    suggestion = await suggest_role(ctx.db, workspace_id=gd.workspace_id, title=ctx.doc.title, opening_text=opening,
                                    complete=ctx.complete, usage=ctx.usage)
    suggested = (suggestion or {}).get("role") or role_hint(ctx.doc.title, ctx.doc.filename)
    if gd.role_basis == "uploader":
        gd.role_suggestion = suggested if suggested and suggested != gd.role else None
    elif suggested:
        gd.role, gd.role_basis, gd.role_suggestion = suggested, "suggested", None
    ctx.state["role"] = gd.role


async def stage_addressees(ctx):
    from services.compliance_graph.applicability import document_addressees

    db, doc = ctx.db, ctx.doc
    found = document_addressees(ctx.pages, doc.title)
    ctx.gd.facts = {**(ctx.gd.facts or {}), "addressees": [
        {"codes": a["codes"], "basis": a["basis"], "span": a["span"], "term": a["term"]} for a in found]}
    for item in found:
        anchor = {"document_id": doc.id, "page_number": item.get("page_number"), "page_position": item.get("page_position"),
                  "start": item.get("start"), "end": item.get("end"), "quote": item["quote"], "span": item["span"],
                  "side": "source", "source": item.get("source", "page")}
        for code in item["codes"]:
            store.upsert_link(db, relation="applies_to", layer="library", from_type="document", from_id=doc.id,
                              to_type="category", to_id=code, basis=item["basis"], anchors=[anchor],
                              attributes={"term": item["term"], "fuzzy": bool(item.get("fuzzy"))},
                              from_document_id=doc.id, run_id=ctx.run_id)
    store.withdraw_untouched_links(
        db, db.query(Link).filter(Link.from_type == "document", Link.from_id == doc.id, Link.relation == "applies_to"),
        ctx.run_id, "The addressees are no longer found in the document")


async def stage_reference(ctx):
    """The instrument's own reference number; links that waited for it are re-pointed."""
    from services.compliance_graph.segment import letter_date, reference_from_pages

    gd = ctx.gd
    own = gd.reference_number or reference_from_pages(ctx.pages)
    gd.reference_number = own
    issued = letter_date(ctx.pages)
    gd.facts = {**(gd.facts or {}), "letter_date": issued.isoformat() if issued else None}
    if own:
        repoint_references(ctx.db, gd)


def _audience_ok(source_access, target_access) -> bool:
    if source_access is None or target_access is None:
        return False
    if source_access.shared_regulatory:
        return bool(target_access.shared_regulatory)
    return bool(target_access.shared_regulatory) or target_access.workspace_id == source_access.workspace_id


def resolve_reference(db, reference, source_document_id) -> list[str]:
    """Current documents carrying this reference number that the source may point at."""
    source_access = db.get(DocumentAccess, source_document_id)
    rows = (
        db.query(GraphDocument.document_id)
        .join(Document, Document.id == GraphDocument.document_id)
        .join(Revision, Revision.id == GraphDocument.document_id)
        .filter(GraphDocument.reference_number == reference, GraphDocument.document_id != source_document_id,
                Document.status == "indexed", Revision.is_current.is_(True))
        .all()
    )
    out = []
    for (document_id,) in rows:
        if _audience_ok(source_access, db.get(DocumentAccess, document_id)):
            out.append(document_id)
    return sorted(out)


def repoint_references(db, gd) -> int:
    """Every citation of this document's reference number now points at the documents carrying it.

    Order-independent: a citation found before its target arrived, or before a
    second document with the same reference (a letter and its template) arrived,
    ends up exactly as one found afterwards. A single target keeps the
    citation's own basis; several targets make each link a suggestion.
    Reviewed links are never withdrawn here.
    """
    reference = gd.reference_number
    carriers = [d for (d,) in db.query(GraphDocument.document_id).filter(GraphDocument.reference_number == reference)]
    active = db.query(Link).filter(Link.status == "active", Link.layer == "library")
    rows = active.filter(Link.to_type == "reference", Link.to_id == reference).all()
    if carriers:
        rows += [link for link in active.filter(Link.to_type == "document", Link.to_document_id.in_(carriers)).all()
                 if (link.attributes or {}).get("reference") == reference]
    groups: dict[tuple, list] = {}
    for link in rows:
        groups.setdefault((link.relation, link.from_type, link.from_id, link.from_document_id), []).append(link)
    changed = 0
    for (relation, from_type, from_id, from_document_id), links in groups.items():
        template = links[0]
        found_basis = next(((l.attributes or {}).get("found_basis") for l in links
                            if (l.attributes or {}).get("found_basis")), None) or (
            next((l.basis for l in links if l.to_type == "reference"), template.basis))
        targets = resolve_reference(db, reference, from_document_id)
        wanted = [("document", t) for t in targets] or [("reference", reference)]
        basis = found_basis if len(wanted) == 1 else "suggested"
        source = db.get(Document, from_document_id) if from_document_id else None
        for to_type, to_id in wanted:
            link, _created = store.upsert_link(
                db, relation=relation, layer="library", from_type=from_type, from_id=from_id, to_type=to_type,
                to_id=to_id, basis=basis, anchors=template.anchors,
                attributes={**(template.attributes or {}), "reference": reference, "found_basis": found_basis},
                rationale=template.rationale, from_document_id=from_document_id,
                to_document_id=to_id if to_type == "document" else None, run_id=template.run_id)
            sync_change_event(db, link, source.title if source else from_id)
        for link in links:
            if (link.to_type, link.to_id) in wanted or link.review_status in store.REVIEWED:
                continue
            link.status = "withdrawn"
            sync_change_event(db, link, None)
            store.event(db, "link", link.id, "resolved", from_status="active", to_status="withdrawn",
                        note=f"Citation of {reference} re-pointed at the instruments that carry it")
            changed += 1
    return changed


def sync_change_event(db, link, trigger_title) -> None:
    """A stated change to one resolved instrument is a library change event; anything less is not."""
    if (link.status == "active" and link.basis == "stated" and link.to_type == "document"
            and link.relation in CHANGE_KIND):
        record_change_event(db, link, trigger_title)
        return
    existing = db.get(ChangeEvent, common.stable_id("change", link.id))
    if existing is not None and existing.status == "active" and link.review_status != "confirmed":
        existing.status = "withdrawn"


def _occurrences(sentences) -> dict[int, int]:
    seen: dict[str, int] = {}
    out = {}
    for s in sentences:
        h = common.text_hash(s.quote)
        out[s.index] = seen.get(h, 0)
        seen[h] = seen.get(h, 0) + 1
    return out


async def stage_requirements(ctx):
    from services.compliance_graph.applicability import obligation_addressees
    from services.compliance_graph.dates import first_date
    from services.compliance_graph.deadlines import parse_deadline
    from services.compliance_graph.extract import classify_requirements
    from services.compliance_graph.segment import BARE_LEAD_IN
    from services.compliance_graph import taxonomy

    db, doc = ctx.db, ctx.doc
    by_index = {s.index: s for s in ctx.sentences}
    # "all OFIs are required to:" carries no duty of its own; its list items do, and get it as context.
    bare = {s.lead_in for s in ctx.sentences
            if s.lead_in is not None and BARE_LEAD_IN.search((by_index[s.lead_in].clean or by_index[s.lead_in].raw).rstrip())}
    candidates = [s for s in ctx.sentences if "requirement" in s.tags and s.index not in bare][:MAX_CANDIDATES]
    occurrences = _occurrences(ctx.sentences)
    total = max(1, len(ctx.sentences))
    issued = common.parse_iso_date((ctx.gd.facts or {}).get("letter_date"))
    cursor = int(ctx.state.get("requirements_next", 0))
    batches = [candidates[i:i + REQUIREMENT_BATCH] for i in range(0, len(candidates), REQUIREMENT_BATCH)]
    for number in range(cursor, len(batches)):
        ctx.check_time()
        db.commit()  # never hold locks across the model call
        items = await classify_requirements(
            db, batches[number], by_index, workspace_id=ctx.gd.workspace_id, title=doc.title,
            regulator=ctx.gd.regulator, complete=ctx.complete, usage=ctx.usage)
        for item in items:
            s = item["sentence"]
            quote = s.quote
            digest = common.text_hash(quote)
            obligation_id = common.stable_id("obl", doc.id, digest, occurrences[s.index])
            codes, basis = obligation_addressees(item["addressee_span"])
            addressee_span = item["addressee_span"]
            if not codes and s.lead_in is not None and s.lead_in in by_index:
                # A list item's subject is the one its introduction names: "Specifically, DFIs are required to:".
                named = taxonomy.match_addressees(by_index[s.lead_in].quote)
                if named:
                    codes = list(dict.fromkeys(code for m in named for code in m.codes))
                    basis = "stated" if all(m.explicit for m in named) else "suggested"
                    addressee_span = ", ".join(dict.fromkeys(m.span for m in named))
            if not codes and item["categories"]:
                codes, basis = item["categories"], "suggested"
            rule = parse_deadline(item["deadline_span"], issued=issued, sentence=quote)
            if rule is None and item["frequency"] and item["frequency"] not in ("event", "once"):
                rule = {"kind": "periodic", "frequency": item["frequency"], "text": item["deadline_span"]}
            obligation, _created = store.upsert_obligation(db, {
                "id": obligation_id, "lineage_id": obligation_id, "document_id": doc.id,
                "occurrence": occurrences[s.index], "position": s.index, "quote": quote,
                "page_number": s.page_number, "page_position": s.page_position, "locator": s.locator,
                "page_char_start": s.start, "page_char_end": s.end, "chunk_id": s.chunk_id,
                "section_heading": s.section_heading, "summary": item["summary"], "kind": item["kind"],
                "addressee_span": addressee_span, "addressee_codes": codes, "addressee_basis": basis,
                "deadline_span": item["deadline_span"], "deadline_rule": rule, "frequency": item["frequency"],
                "effective_span": item["effective_span"], "effective_date": first_date(item["effective_span"] or ""),
                "topics": item["topics"], "text_hash": digest,
            }, ctx.run_id)
            for return_id in taxonomy.suggest_returns(f"{quote} {item['summary'] or ''}"):
                store.upsert_link(db, relation="filed_via", layer="library", from_type="obligation",
                                  from_id=obligation.lineage_id, to_type="return", to_id=return_id, basis="suggested",
                                  anchors=[_anchor(doc.id, s)], from_document_id=doc.id, run_id=ctx.run_id)
        ctx.state["requirements_next"] = number + 1
        ctx.state["position_total"] = total
        _save_state(ctx)
    store.withdraw_untouched_obligations(db, doc.id, ctx.run_id)
    store.withdraw_untouched_links(
        db, db.query(Link).filter(Link.relation == "filed_via", Link.from_document_id == doc.id),
        ctx.run_id, "No longer suggested by the latest extraction")
    _run_log(ctx, "requirements", "done", {"candidates": len(candidates), "batches": len(batches)})


def _items(obligations, total):
    from services.compliance_graph.lineage import Item

    return [Item(key=o.id, text=o.quote, text_hash=o.text_hash, occurrence=o.occurrence, section=o.section_heading,
                 position=(o.position or 0) / max(1, total), lineage=o.lineage_id) for o in obligations]


async def stage_lineage(ctx):
    """Requirements of a new version inherit the lineage of their earlier wording."""
    from services.compliance_graph.lineage import match

    db, gd = ctx.db, ctx.gd
    previous = gd.previous_document_id
    if not previous:
        return
    old_rows = db.query(Obligation).filter(Obligation.document_id == previous, Obligation.status == "active").all()
    new_rows = db.query(Obligation).filter(Obligation.document_id == gd.document_id, Obligation.status == "active").all()
    old_total = max([o.position or 0 for o in old_rows] + [1])
    new_total = max([o.position or 0 for o in new_rows] + [1])
    diff = match(_items(old_rows, old_total), _items(new_rows, new_total))
    by_id = {o.id: o for o in new_rows}
    for old, new in diff.unchanged + diff.modified:
        row = by_id[new.key]
        if row.review_status not in store.REVIEWED:
            row.lineage_id = old.lineage
    if not (diff.modified or diff.removed or diff.added):
        return
    old_quotes = {o.id: o.quote for o in old_rows}
    details = {
        "modified": [{"lineage_id": o.lineage, "old_id": o.key, "new_id": n.key, "old_quote": old_quotes.get(o.key),
                      "new_quote": by_id[n.key].quote} for o, n in diff.modified],
        "removed": [{"lineage_id": o.lineage, "old_id": o.key, "quote": old_quotes.get(o.key)} for o in diff.removed],
        "added": [by_id[n.key].lineage_id for n in diff.added],
    }
    event_id = common.stable_id("change", "new_version", previous, gd.document_id)
    summary = (f"New version of “{ctx.doc.title}”: {len(diff.modified)} requirement(s) reworded, "
               f"{len(diff.removed)} no longer appear, {len(diff.added)} added.")
    existing = db.get(ChangeEvent, event_id)
    if existing is None:
        db.add(ChangeEvent(id=event_id, kind="new_version", subject_document_id=previous,
                           trigger_document_id=gd.document_id, details=details, summary=summary,
                           created_at=common.utcnow()))
    else:
        existing.details, existing.summary, existing.status = details, summary, "active"


async def stage_relations(ctx):
    from services.compliance_graph.relations import (CHANGE_WORDS, EXCLUDED_OBJECT, LIBRARY_RELATIONS,
                                                     RELATION_SYSTEM, deterministic_findings, relation_schema)
    from services.compliance_graph.llm import ask_json

    db, doc, gd = ctx.db, ctx.doc, ctx.gd
    relevant = [s for s in ctx.sentences if "relation" in s.tags]
    findings = deterministic_findings(relevant, gd.reference_number)
    # An Act the instrument is issued under is not also listed as a plain citation.
    issued_under = {f.mention.key for f in findings if f.relation == "issued_under"}
    findings = [f for f in findings
                if not (f.relation == "references" and f.mention.kind == "act" and f.mention.key in issued_under)]
    produced: list[tuple] = []

    def link_finding(finding, relation, basis, rationale=None):
        mention = finding.mention
        anchor = _anchor(doc.id, finding.sentence, cue=finding.cue_span, mention=mention.span)
        found_basis = basis  # before any downgrade for an ambiguous target; repoint_references needs it
        if mention.kind == "act":
            targets, to_type = [mention.key], "act"
        else:
            resolved = resolve_reference(db, mention.key, doc.id)
            if not resolved:
                targets, to_type = [mention.key], "reference"
            else:
                targets, to_type = resolved, "document"
                if len(resolved) > 1:
                    basis = "suggested"  # several instruments share this reference
        for target in targets:
            link, created = store.upsert_link(
                db, relation=relation, layer="library", from_type="document", from_id=doc.id, to_type=to_type,
                to_id=target, basis=basis, anchors=[anchor],
                attributes={"reference": mention.key if mention.kind == "reference" else None,
                            "act": mention.key if mention.kind == "act" else None,
                            "found_basis": found_basis if mention.kind == "reference" else None},
                rationale=rationale, from_document_id=doc.id,
                to_document_id=target if to_type == "document" else None, run_id=ctx.run_id)
            produced.append((link, created))

    for finding in findings:
        link_finding(finding, finding.relation, finding.basis)

    # The model may read an implicit relation into a citation; that is only ever a suggestion.
    # The change is often stated apart from the citation ("Your attention is drawn to our
    # letter ref ... " then "Management has approved an extension of the timeline"), so the
    # instrument's own change sentences and title go along as context.
    changes = [s for s in ctx.sentences
               if CHANGE_WORDS.search(s.clean or s.raw) and not EXCLUDED_OBJECT.search(s.clean or s.raw)]
    describes_change = bool(changes) or bool(CHANGE_WORDS.search(doc.title or ""))
    ambiguous = [f for f in findings if f.relation == "references" and f.mention.kind == "reference"
                 and (describes_change or CHANGE_WORDS.search(f.sentence.clean or f.sentence.raw))]
    if ambiguous:
        db.commit()
        payload = [{"id": f"r{i}", "sentence": f.sentence.quote, "mention": f.mention.span}
                   for i, f in enumerate(ambiguous[:20])]
        context = {"title": doc.title, "change_sentences": [s.quote[:400] for s in changes[:4]]}
        import json

        raw = await ask_json(db, workspace_id=gd.workspace_id,
                             prompt=json.dumps({"instrument": context, "items": payload}, ensure_ascii=False),
                             system=RELATION_SYSTEM, schema=relation_schema(), max_tokens=40 * len(payload) + 100,
                             complete=ctx.complete, usage=ctx.usage)
        for item in (raw or {}).get("items", []) if isinstance((raw or {}).get("items"), list) else []:
            try:
                finding = ambiguous[int(str(item.get("id", "")).lstrip("r"))]
            except (ValueError, IndexError):
                continue
            relation = item.get("relation")
            if relation in LIBRARY_RELATIONS and relation not in ("references", "issued_under"):
                link_finding(finding, relation, "suggested", rationale=f"Iroko reads this sentence as: {relation}")

    store.withdraw_untouched_links(
        db, db.query(Link).filter(Link.from_type == "document", Link.from_id == doc.id,
                                  Link.relation.in_(LIBRARY_RELATIONS)),
        ctx.run_id, "No longer found in the latest extraction")
    # A stated change to another instrument is a library fact every reader of that instrument should see.
    for link, created in produced:
        if link.basis == "stated" and link.to_type == "document" and link.relation in (
                "amends", "supersedes", "revokes", "extends_deadline_of"):
            record_change_event(db, link, doc.title)


CHANGE_KIND = {"amends": "amended_by", "supersedes": "superseded_by", "revokes": "revoked_by",
               "extends_deadline_of": "deadline_extended"}


def record_change_event(db, link, trigger_title) -> ChangeEvent:
    event_id = common.stable_id("change", link.id)
    kind = CHANGE_KIND[link.relation]
    verb = {"amended_by": "amends", "superseded_by": "supersedes", "revoked_by": "revokes",
            "deadline_extended": "extends a deadline in"}[kind]
    target = db.get(Document, link.to_id)
    summary = f"“{trigger_title}” {verb} “{target.title if target else link.to_id}”."
    row = store.get_current(db, ChangeEvent, event_id)
    if row is None:
        row = ChangeEvent(id=event_id, kind=kind, subject_document_id=link.to_id, trigger_document_id=link.from_id,
                          link_id=link.id, details={"basis": link.basis, "scope": (link.attributes or {}).get("scope")},
                          summary=summary, created_at=common.utcnow())
        db.add(row)
    else:
        row.status = "active"
    return row


async def stage_effective(ctx):
    from services.compliance_graph.relations import effective_date

    gd = ctx.gd
    if gd.effective_basis == "confirmed":
        return
    found = effective_date([s for s in ctx.sentences if "effective" in s.tags], ctx.pages)
    if not found:
        gd.effective_date, gd.effective_basis, gd.effective_anchor = None, None, None
        return
    s = found["sentence"]
    gd.effective_date = found["date"]
    gd.effective_basis = found["basis"]
    gd.effective_anchor = _anchor(ctx.doc.id, s, span=found["span"], note=found.get("note"))


async def stage_controls(ctx):
    from services.compliance_graph.extract import CONTROL_CUES, classify_controls

    db, doc, gd = ctx.db, ctx.doc, ctx.gd
    candidates = [s for s in ctx.sentences if CONTROL_CUES.search(s.clean or s.raw)][:MAX_CANDIDATES]
    by_index = {s.index: s for s in ctx.sentences}
    occurrences = _occurrences(ctx.sentences)
    cursor = int(ctx.state.get("controls_next", 0))
    batches = [candidates[i:i + CONTROL_BATCH] for i in range(0, len(candidates), CONTROL_BATCH)]
    for number in range(cursor, len(batches)):
        ctx.check_time()
        db.commit()
        items = await classify_controls(db, batches[number], by_index, workspace_id=gd.workspace_id,
                                        title=doc.title, complete=ctx.complete, usage=ctx.usage)
        for item in items:
            upsert_extracted_control(db, ctx, item, occurrences[item["sentence"].index])
        ctx.state["controls_next"] = number + 1
        _save_state(ctx)
    _run_log(ctx, "controls", "done", {"candidates": len(candidates), "batches": len(batches)})


def upsert_extracted_control(db, ctx, item, occurrence) -> Control:
    """Controls are keyed by (policy lineage, wording, occurrence): unchanged wording keeps its row."""
    s = item["sentence"]
    gd = ctx.gd
    digest = common.text_hash(s.quote)
    key = common.stable_id("ctl", gd.lineage_key, digest, occurrence)
    row = db.query(Control).filter(Control.workspace_id == gd.workspace_id, Control.extraction_key == key).first()
    machine = {"name": item["name"], "summary": item["summary"], "performer_span": item["performer_span"],
               "frequency": item["frequency"], "evidence_expected": item["evidence_expected"], "topics": item["topics"]}
    anchor = {"document_id": ctx.doc.id, "quote": s.quote, "page_number": s.page_number, "page_position": s.page_position,
              "locator": s.locator, "page_char_start": s.start, "page_char_end": s.end, "chunk_id": s.chunk_id,
              "section_heading": s.section_heading}
    if row is None:
        row = Control(id=generate_id(), workspace_id=gd.workspace_id, extraction_key=key, basis="stated",
                      review_status="proposed", status="active", text_hash=digest, run_id=ctx.run_id,
                      anchor_history=[], created_at=common.utcnow(), updated_at=common.utcnow(), **machine, **anchor)
        db.add(row)
        store.event(db, "control", row.id, "extracted", workspace_id=gd.workspace_id, to_status="proposed",
                    snapshot={"name": row.name, "quote": s.quote})
        return row
    if row.document_id != ctx.doc.id:
        row.anchor_history = list(row.anchor_history or []) + [{
            "document_id": row.document_id, "quote": row.quote, "page_number": row.page_number,
            "replaced_at": common.utcnow().isoformat()}]
    for name, value in anchor.items():
        setattr(row, name, value)
    if row.review_status in store.REVIEWED:
        current = {k: getattr(row, k) for k in machine}
        if current != machine:
            row.proposal = machine
    else:
        for name, value in machine.items():
            setattr(row, name, value)
    row.status = "active"
    row.run_id = ctx.run_id
    row.updated_at = common.utcnow()
    return row


async def stage_control_lineage(ctx):
    """Reworded controls keep their identity; controls no longer in the policy are retired."""
    from services.compliance_graph.lineage import Item, match

    db, gd = ctx.db, ctx.gd
    rows = db.query(Control).filter(Control.workspace_id == gd.workspace_id, Control.status == "active",
                                    Control.extraction_key.isnot(None)).all()
    lineage_rows = [r for r in rows if r.extraction_key and _control_in_lineage(db, r, gd.lineage_key)]
    fresh = [r for r in lineage_rows if r.run_id == ctx.run_id and r.document_id == ctx.doc.id]
    stale = [r for r in lineage_rows if r.run_id != ctx.run_id]
    if not stale:
        return

    def item(r):
        # Position is not comparable across versions of a policy; the section and wording decide.
        return Item(key=r.id, text=r.quote or "", text_hash=r.text_hash or "", occurrence=0,
                    section=r.section_heading, position=0.5, lineage=r.id)

    diff = match([item(r) for r in stale], [item(r) for r in fresh])
    by_id = {r.id: r for r in lineage_rows}
    anchor_fields = ("document_id", "quote", "page_number", "page_position", "locator", "page_char_start",
                     "page_char_end", "chunk_id", "section_heading", "text_hash", "extraction_key")
    for old, new in diff.modified:
        keep, merged = by_id[old.key], by_id[new.key]
        values = {name: getattr(merged, name) for name in anchor_fields}
        # The fresh row only existed for this run; remove it before its key moves to the kept row.
        db.delete(merged)
        db.flush()
        if keep.review_status in store.REVIEWED and keep.review_status != "rejected":
            keep.review_status = "needs_re_review"
            keep.review_note = "The policy wording changed in a new version"
        keep.anchor_history = list(keep.anchor_history or []) + [{
            "document_id": keep.document_id, "quote": keep.quote, "replaced_at": common.utcnow().isoformat()}]
        for name, value in values.items():
            setattr(keep, name, value)
        keep.run_id = ctx.run_id
        store.event(db, "control", keep.id, "reworded", workspace_id=gd.workspace_id,
                    snapshot={"new_quote": keep.quote})
    db.flush()
    for old in diff.removed:
        row = by_id[old.key]
        if row.basis == "manual":
            continue
        if row.document_id == ctx.doc.id and row.review_status in store.REVIEWED:
            # Same version, different reading by the model: never retire what a person confirmed.
            row.proposal = {"withdraw": True, "reason": "Not found as a control in the latest extraction"}
            continue
        row.status = "retired"
        store.event(db, "control", row.id, "retired", workspace_id=gd.workspace_id, from_status="active",
                    to_status="retired", note="No longer found in the latest version of the policy")


def _control_in_lineage(db, control, lineage_key) -> bool:
    if not control.document_id:
        return False
    rev = db.get(Revision, control.document_id)
    return bool(rev and rev.source_key == lineage_key)


async def stage_evidence(ctx):
    from services.compliance_graph.dates import find_dates
    from services.compliance_graph.extract import describe_evidence
    from services.compliance_graph.segment import mask_markup

    db, gd = ctx.db, ctx.gd
    text = "\n\n".join(mask_markup(p.text or "") for p in ctx.pages)
    db.commit()
    found = await describe_evidence(db, workspace_id=gd.workspace_id, title=ctx.doc.title, text=text,
                                    complete=ctx.complete, usage=ctx.usage)
    if not found:
        return
    period = find_dates(found["period_span"] or "")
    record_date = find_dates(found["record_date_span"] or "")
    anchor = None
    if found.get("activity_span"):
        for p in ctx.pages:
            where = common.locate(found["activity_span"], mask_markup(p.text or ""))
            if where:
                anchor = {"page_number": p.page_number, "page_position": p.position, "start": where[0], "end": where[1]}
                break
    gd.facts = {**(gd.facts or {}), "evidence": {
        **found,
        "anchor": anchor,
        "period_start": period[0].value.isoformat() if period else None,
        "period_end": period[-1].value.isoformat() if len(period) > 1 else (period[0].value.isoformat() if period else None),
        "record_date": record_date[0].value.isoformat() if record_date else None,
    }}


# ─── Backfill ────────────────────────────────────────────────────────────────


def backfill(db, *, document_id=None, workspace_id=None, force=False) -> int:
    """Queue extraction for current, indexed documents (all, one, or one workspace's)."""
    from models.database import Base, engine
    import models.compliance_graph  # noqa: F401  (registers the tables)

    prepare_session(db)
    Base.metadata.create_all(bind=engine, tables=[t for name, t in Base.metadata.tables.items() if name.startswith("cg_")])
    query = (db.query(Document.id).join(Revision, Revision.id == Document.id)
             .filter(Document.status == "indexed", Revision.is_current.is_(True)))
    if document_id:
        query = query.filter(Document.id == document_id)
    if workspace_id:
        query = query.join(DocumentAccess, DocumentAccess.document_id == Document.id).filter(
            DocumentAccess.workspace_id == workspace_id)
    queued = 0
    for (doc_id,) in query.all():
        gd = db.get(GraphDocument, doc_id)
        if gd is not None and gd.extraction_status == "done" and not force:
            continue
        if gd is not None and force:
            gd.stage_state = {}
            gd.prompt_version = None
        enqueue(db, "graph", doc_id)
        queued += 1
    db.commit()
    return queued
