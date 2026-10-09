"""
The workspace sync job: graph_ws:{workspace_id}.

Idempotent and incremental. Each run:
  1. suggests links from the workspace's controls to requirements that apply,
     or may apply, to it, judging only text pairs it has never judged before;
  2. suggests which controls or requirements each evidence record supports;
  3. turns library change events and the workspace's own policy changes into
     impacts on ITS links, flagging confirmed ones for re-review;
  4. keeps one task per open impact and one review task current.

Nothing here reads or writes another workspace's rows: every read goes
through visibility.py with this workspace's scope.
"""

from __future__ import annotations

from collections import defaultdict

from ingestion.models import DocumentAccess, Job
from ingestion.queue import enqueue, finish
from models.compliance_graph import (ChangeEvent, Control, GraphDocument, Impact, Link, Obligation,
                                     WorkspaceSync)
from models.database import Document
from services.compliance_graph import common, core, store
from services.compliance_graph.mapping import POSITIVE, judge, rank
from services.compliance_graph.visibility import for_workspace, is_document_visible


async def workspace_job(ctx, key, token, workspace_id):
    db = ctx.db
    scope = for_workspace(workspace_id)
    sync = db.get(WorkspaceSync, workspace_id)
    if sync is None:
        sync = WorkspaceSync(workspace_id=workspace_id, rerun_requested=False)
        db.add(sync)
    sync.rerun_requested = False  # this run covers everything requested so far
    sync.last_run_at = common.utcnow()
    db.commit()

    await suggest_control_mappings(ctx, scope)
    await suggest_evidence_links(ctx, scope)
    apply_impacts(db, scope)
    refresh_tasks(db, scope)

    sync = db.get(WorkspaceSync, workspace_id)
    sync.outage_since, sync.last_error = None, None
    db.commit()
    finish(db, key, token)
    db.refresh(sync)
    if sync.rerun_requested:
        sync.rerun_requested = False
        enqueue(db, "graph_ws", workspace_id)
        db.commit()


# ─── Anchors ─────────────────────────────────────────────────────────────────


def control_anchor(control: Control, span=None) -> dict:
    return {"kind": "control", "side": "from", "control_id": control.id, "document_id": control.document_id,
            "page_number": control.page_number, "page_position": control.page_position,
            "start": control.page_char_start, "end": control.page_char_end, "chunk_id": control.chunk_id,
            "quote": control.quote or control.name, "span": span}


def obligation_anchor(o: Obligation, span=None, side="to") -> dict:
    return {"kind": "obligation", "side": side, "obligation_id": o.id, "document_id": o.document_id,
            "page_number": o.page_number, "page_position": o.page_position, "start": o.page_char_start,
            "end": o.page_char_end, "chunk_id": o.chunk_id, "quote": o.quote, "span": span}


def evidence_anchor(gd: GraphDocument, span=None) -> dict:
    facts = (gd.facts or {}).get("evidence") or {}
    where = facts.get("anchor") or {}
    return {"kind": "evidence", "side": "from", "document_id": gd.document_id,
            "page_number": where.get("page_number"), "page_position": where.get("page_position"),
            "start": where.get("start"), "end": where.get("end"),
            "quote": facts.get("activity_span") or facts.get("activity"), "span": span}


# ─── Suggestions ─────────────────────────────────────────────────────────────


def _requirement_targets(db, scope):
    codes = core.profile(db, scope.workspace_id)["category_codes"]
    obligations = core.visible_obligations(db, scope, current=True)
    applicable = core.applicability_of(db, scope, obligations, codes)
    titles = core.document_titles(db, [o.document_id for o in obligations])
    targets, seen = [], set()
    for o in obligations:
        if o.lineage_id in seen or applicable.get(o.lineage_id) in ("not_addressed", "not_applicable"):
            continue
        seen.add(o.lineage_id)
        targets.append({"key": f"obligation:{o.lineage_id}", "text": o.quote, "summary": o.summary,
                        "topics": o.topics or [], "hash": o.text_hash, "obligation": o,
                        "context": _context(titles.get(o.document_id) or "A regulation", o.section_heading)})
    return targets


def _context(title, section=None) -> str:
    """Which document (and section) a text is in, so the judge knows what "this policy" refers to."""
    return f"{title} — {section}" if section and section.strip().lower() != (title or "").strip().lower() else title


async def suggest_control_mappings(ctx, scope):
    db = ctx.db
    targets = _requirement_targets(db, scope)
    if not targets:
        return
    controls = [c for c in core.active_controls(db, scope) if c.review_status != "rejected"]
    titles = core.document_titles(db, [c.document_id for c in controls])
    for control in controls:
        ctx.check_time()
        text = control.quote or " ".join(filter(None, [control.name, control.summary]))
        subject = {"text": text, "summary": control.summary, "hash": control.text_hash or common.text_hash(text),
                   "context": _context(titles.get(control.document_id) or "Entered by your team", control.section_heading)}
        top = rank(f"{control.name} {text} {control.summary or ''}", control.topics, targets)
        if not top:
            continue
        results = await judge(db, kind="control", workspace_id=scope.workspace_id, subject=subject, targets=top,
                              complete=ctx.complete, usage=ctx.usage)
        for target in top:
            result = results.get(target["key"])
            if not result or result["relation"] not in POSITIVE:
                continue
            o = target["obligation"]
            store.upsert_link(
                db, relation="addresses", layer="workspace", workspace_id=scope.workspace_id,
                from_type="control", from_id=control.id, to_type="obligation", to_id=o.lineage_id,
                basis="suggested",
                anchors=[control_anchor(control, result["subject_span"]), obligation_anchor(o, result["target_span"])],
                attributes={"coverage": POSITIVE[result["relation"]]}, rationale=result["rationale"],
                from_document_id=control.document_id, to_document_id=o.document_id)
        db.commit()


async def suggest_evidence_links(ctx, scope):
    db = ctx.db
    documents = [gd for gd in core.evidence_documents(db, scope)
                 if gd.workspace_id == scope.workspace_id and ((gd.facts or {}).get("evidence") or {}).get("activity")]
    if not documents:
        return
    controls = [c for c in core.active_controls(db, scope) if c.review_status != "rejected"]
    titles = core.document_titles(db, [c.document_id for c in controls])
    targets = [{"key": f"control:{c.id}", "text": c.quote or c.name, "summary": c.summary, "topics": c.topics or [],
                "hash": c.text_hash or common.text_hash(c.quote or c.name), "control": c,
                "context": _context(titles.get(c.document_id) or "Entered by your team", c.section_heading)}
               for c in controls]
    targets += _requirement_targets(db, scope)
    if not targets:
        return
    for gd in documents:
        ctx.check_time()
        facts = gd.facts["evidence"]
        text = " ".join(filter(None, [facts.get("activity_span"), facts.get("activity")]))
        subject = {"text": text, "summary": facts.get("activity"),
                   "hash": common.text_hash(f"{text} {facts.get('period_span') or ''}"),
                   "context": gd.title or "A record"}
        top = rank(f"{gd.title or ''} {text}", facts.get("topics"), targets)
        if not top:
            continue
        results = await judge(db, kind="evidence", workspace_id=scope.workspace_id, subject=subject, targets=top,
                              complete=ctx.complete, usage=ctx.usage)
        for target in top:
            result = results.get(target["key"])
            if not result or result["relation"] not in POSITIVE:
                continue
            if "control" in target:
                c = target["control"]
                to_type, to_id, to_doc = "control", c.id, c.document_id
                anchor = control_anchor(c, result["target_span"])
                anchor["side"] = "to"
            else:
                o = target["obligation"]
                to_type, to_id, to_doc = "obligation", o.lineage_id, o.document_id
                anchor = obligation_anchor(o, result["target_span"])
            store.upsert_link(
                db, relation="evidences", layer="workspace", workspace_id=scope.workspace_id,
                from_type="document", from_id=gd.document_id, to_type=to_type, to_id=to_id, basis="suggested",
                anchors=[evidence_anchor(gd, result["subject_span"]), anchor],
                attributes={"coverage": POSITIVE[result["relation"]], "period_start": facts.get("period_start"),
                            "period_end": facts.get("period_end"), "record_date": facts.get("record_date")},
                rationale=result["rationale"], from_document_id=gd.document_id, to_document_id=to_doc)
        db.commit()


# ─── Impacts ─────────────────────────────────────────────────────────────────


def _flag(db, link, reason, flagged):
    """Confirmed links need a person to look again; suggestions are left as they are."""
    if link.review_status != "confirmed":
        return
    link.review_status = "needs_re_review"
    link.stale_reason = reason
    flagged.append({"link_id": link.id, "previous": "confirmed", "reason": reason})
    store.event(db, "link", link.id, "flagged_for_re_review", workspace_id=link.workspace_id,
                from_status="confirmed", to_status="needs_re_review", note=reason)


def withdraw_impact(db, impact):
    """A change that turned out not to happen (its link was rejected) releases its flags."""
    for item in (impact.affected or {}).get("flagged", []):
        link = db.get(Link, item["link_id"])
        if link is not None and link.review_status == "needs_re_review" and link.stale_reason == item["reason"]:
            link.review_status, link.stale_reason = item["previous"], None
            store.event(db, "link", link.id, "re_review_withdrawn", workspace_id=link.workspace_id,
                        from_status="needs_re_review", to_status=item["previous"],
                        note="The change that raised it was rejected")
    impact.status = "withdrawn"


CHANGE_REASON = {
    "amended_by": "amends", "revoked_by": "revokes", "superseded_by": "supersedes",
    "deadline_extended": "extends a deadline in",
}


def _before(moment, change_time) -> bool:
    """Whether a link's creation or review predates a change (unknown times count as before)."""
    return moment is None or change_time is None or moment < change_time


def apply_impacts(db, scope) -> None:
    ws = scope.workspace_id
    links = core.workspace_links(db, scope)
    to_lineage = defaultdict(list)
    by_control = defaultdict(list)
    for link in links:
        if link.review_status == "rejected":
            continue
        if link.to_type == "obligation":
            to_lineage[link.to_id].append(link)
        if link.from_type == "control":
            by_control[link.from_id].append(link)
        if link.to_type == "control":
            by_control[link.to_id].append(link)
    existing = {i.dedupe_key: i for i in db.query(Impact).filter(Impact.workspace_id == ws)}
    titles = core.document_titles(db, [e.trigger_document_id for e in db.query(ChangeEvent)]
                                  + [e.subject_document_id for e in db.query(ChangeEvent)])

    for event in db.query(ChangeEvent).order_by(ChangeEvent.created_at):
        dedupe = f"event:{event.id}"
        impact = existing.get(dedupe)
        if event.status == "withdrawn":
            if impact is not None and impact.status != "withdrawn":
                withdraw_impact(db, impact)
            continue
        if impact is not None or not is_document_visible(db, scope, event.trigger_document_id, current=False):
            continue
        affected: list[tuple[Link, str]] = []
        if event.kind == "new_version":
            for item in (event.details or {}).get("modified", []):
                affected += [(link, "The requirement was reworded in a new version of the document")
                             for link in to_lineage.get(item["lineage_id"], [])]
            for item in (event.details or {}).get("removed", []):
                affected += [(link, "The requirement no longer appears in the new version of the document")
                             for link in to_lineage.get(item["lineage_id"], [])]
        else:
            change = db.get(Link, event.link_id) if event.link_id else None
            if change is None or change.status != "active" or change.review_status == "rejected":
                continue
            if change.basis != "stated" and change.review_status != "confirmed":
                continue  # a suggestion changes nothing until a reviewer confirms it
            lineages = {row[0] for row in db.query(Obligation.lineage_id)
                        .filter(Obligation.document_id == event.subject_document_id)}
            verb = CHANGE_REASON.get(event.kind, "changes")
            reason = (f"“{titles.get(event.trigger_document_id, 'A newer instrument')}” {verb} "
                      f"“{titles.get(event.subject_document_id, 'this instrument')}”")
            for lineage in lineages:
                affected += [(link, reason) for link in to_lineage.get(lineage, [])]
        # A change touches only links that existed when it happened, and only a confirmation made
        # before it needs another look: a team that confirms a mapping after the change has seen it.
        affected = [(link, reason) for link, reason in affected if _before(link.created_at, event.created_at)]
        if not affected:
            continue
        flagged: list[dict] = []
        if event.kind != "deadline_extended":  # an extension changes dates, not what the control must do
            for link, reason in affected:
                if _before(link.reviewed_at, event.created_at):
                    _flag(db, link, reason, flagged)
        db.add(Impact(
            workspace_id=ws, event_id=event.id, dedupe_key=dedupe, kind=event.kind, summary=event.summary,
            affected={"links": sorted({link.id for link, _r in affected}), "flagged": flagged,
                      "lineages": sorted({link.to_id for link, _r in affected if link.to_type == "obligation"}),
                      "controls": sorted({link.from_id for link, _r in affected if link.from_type == "control"})},
            status="open", created_at=common.utcnow()))

    for control in db.query(Control).filter(Control.workspace_id == ws, Control.status == "retired"):
        dedupe = f"control_retired:{control.id}"
        related = by_control.get(control.id, [])
        if dedupe in existing or not related:
            continue
        flagged: list[dict] = []
        for link in related:
            _flag(db, link, "The control is no longer in the latest version of the policy", flagged)
        db.add(Impact(workspace_id=ws, dedupe_key=dedupe, kind="control_retired",
                      summary=f"“{control.name}” is no longer in the latest version of the policy; "
                              f"{len(related)} link(s) that relied on it need a look.",
                      affected={"links": [link.id for link in related], "flagged": flagged, "controls": [control.id]},
                      status="open", created_at=common.utcnow()))

    for control in db.query(Control).filter(Control.workspace_id == ws, Control.status == "active",
                                            Control.review_status == "needs_re_review"):
        dedupe = f"control_reworded:{control.id}:{control.text_hash}"
        related = [link for link in by_control.get(control.id, []) if link.from_id == control.id]
        if dedupe in existing:
            continue
        flagged: list[dict] = []
        for link in related:
            _flag(db, link, "The control's wording changed in a new version of the policy", flagged)
        db.add(Impact(workspace_id=ws, dedupe_key=dedupe, kind="control_reworded",
                      summary=f"The wording of “{control.name}” changed in a new version of the policy.",
                      affected={"links": [link.id for link in related], "flagged": flagged, "controls": [control.id]},
                      status="open", created_at=common.utcnow()))

    visible_ids = {link.id for link in links}
    for link in db.query(Link).filter(Link.workspace_id == ws, Link.status == "active",
                                      Link.review_status != "rejected"):
        dedupe = f"unavailable:{link.id}"
        if link.id in visible_ids or dedupe in existing:
            continue
        db.add(Impact(workspace_id=ws, dedupe_key=dedupe, kind="source_unavailable",
                      summary="A document one of your links relied on is no longer available in your library "
                              "(archived, rejected or no longer shared).",
                      affected={"links": [link.id]}, status="open", created_at=common.utcnow()))
    db.commit()


# ─── Tasks ───────────────────────────────────────────────────────────────────


def _library_pending(db, ws) -> int:
    """Regulation facts this workspace's members review: facts of documents it owns."""
    owned = [row[0] for row in db.query(DocumentAccess.document_id).filter(DocumentAccess.workspace_id == ws)]
    if not owned:
        return 0
    links = (db.query(Link).filter(Link.workspace_id.is_(None), Link.from_document_id.in_(owned),
                                   Link.status == "active", Link.basis == "suggested",
                                   Link.review_status == "proposed").count())
    documents = (db.query(GraphDocument).filter(GraphDocument.document_id.in_(owned))
                 .filter((GraphDocument.role_suggestion.isnot(None)) | (GraphDocument.effective_basis == "suggested")
                         | (GraphDocument.role_basis == "suggested")).count())
    unshared_versions = 0
    for access in db.query(DocumentAccess).filter(DocumentAccess.workspace_id == ws,
                                                  DocumentAccess.shared_regulatory.is_(True)):
        doc = db.get(Document, access.document_id)
        if doc is None or doc.status != "superseded":
            continue
        unshared_versions += int(bool(_newer_unshared(db, access.document_id)))
    return links + documents + unshared_versions


def _newer_unshared(db, document_id) -> str | None:
    from ingestion.models import Revision

    rev = db.get(Revision, document_id)
    if rev is None:
        return None
    newer = (db.query(Revision).filter(Revision.source_key == rev.source_key, Revision.is_current.is_(True),
                                       Revision.created_at > rev.created_at).first())
    if newer is None:
        return None
    access = db.get(DocumentAccess, newer.id)
    doc = db.get(Document, newer.id)
    if doc is not None and doc.status == "indexed" and access is not None and not access.shared_regulatory:
        return newer.id
    return None


def refresh_tasks(db, scope) -> None:
    from services.workflow_service import close_graph_task, upsert_graph_task

    ws = scope.workspace_id
    for impact in db.query(Impact).filter(Impact.workspace_id == ws):
        if impact.status == "open" and not impact.task_id:
            task = upsert_graph_task(
                db, workspace_id=ws, source_type="change_impact", source_id=impact.id, title=impact.summary,
                description="Open the Knowledge Graph's Changes tab to see what changed and which of your "
                            "controls and evidence links need another look.",
                priority="high", sla_hours=72)
            impact.task_id = task.id
        elif impact.status in ("acknowledged", "withdrawn") and impact.task_id:
            close_graph_task(db, "change_impact", impact.id)

    links = core.workspace_links(db, scope)
    pending = sum(1 for link in links if link.review_status in ("proposed", "needs_re_review"))
    pending += (db.query(Control).filter(Control.workspace_id == ws, Control.status == "active",
                                         Control.review_status == "proposed").count())
    if pending:
        upsert_graph_task(
            db, workspace_id=ws, source_type="graph_review", source_id=f"workspace:{ws}",
            title=f"Review {pending} compliance-graph item(s) Iroko suggested",
            description="Iroko suggested how your controls, evidence and requirements connect. Confirm or reject "
                        "each suggestion in the Knowledge Graph's Review tab; nothing is treated as confirmed "
                        "until you do.",
            priority="medium", sla_hours=168)
    else:
        close_graph_task(db, "graph_review", f"workspace:{ws}")

    library = _library_pending(db, ws)
    if library:
        upsert_graph_task(
            db, workspace_id=ws, source_type="graph_review", source_id=f"library:{ws}",
            title=f"Review {library} regulation fact(s) Iroko suggested",
            description="Suggested relationships between instruments, applicability, effective dates and document "
                        "roles, plus newer versions waiting to be shared. Review them in the Knowledge Graph.",
            priority="medium", sla_hours=168)
    else:
        close_graph_task(db, "graph_review", f"library:{ws}")
    db.commit()
