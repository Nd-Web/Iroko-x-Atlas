"""Compliance-graph extraction evaluation: known facts from real CBN documents, checked on isolated SQLite.

Loads the corpus snapshot (.dist/rag-evaluation/corpus.json, made by
`python scripts/evaluate_document_answers.py snapshot`) into a fresh SQLite file, adds the gold
set's synthetic letters, runs the real graph:{document} job on every document as a shared
library instrument, then checks tests/evals/graph_gold.json:

  reference / letter_date / role    facts about the instrument itself
  addressee / no_addressee          who it is addressed to, and with what basis
  applicability                     what a workspace with given licences would be shown
  link / no_link / isolated_from    relationships, including the traps (a licence revocation is not
                                    an instrument revocation; "(as amended)" is not an amendment;
                                    a shared subject is not a relationship)
  effective / not_effective         the instrument's own effective date, never one it reports
  change_event / no_change_event    library change events
  requirement / no_requirement      model-dependent: which sentences are requirements, their kind,
  requirement_count                 addressee and computed deadline

Requirement recall is the share of `requirement` checks met. --offline swaps the model for one
that declines every candidate, so only deterministic checks run and nothing is sent to an API.
Otherwise --model nano (default) uses the Chat Completions test deployment, and --model sol
uses production's Responses model exactly as the worker does (no fallback); both on isolated SQLite.

--mapping then sets up a pilot MFB workspace with its own policy, procedure and records
(tests/evals/graph_fixtures), runs their extraction and the graph_ws sync, and checks the
gold set's "mapping" section: which controls are found, which requirements each is suggested
to address, which records evidence them, and that related-sounding clauses map to nothing.

Run from backend:
  python scripts/evaluate_graph_extraction.py [--offline] [--model nano|sol] [--case ID ...] [--mapping]
Writes .dist/rag-evaluation/graph-extraction-<time>.json. Nothing touches production data.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))
GOLD = BACKEND / "tests" / "evals" / "graph_gold.json"
DOCUMENT_RELATIONS = ("amends", "supersedes", "revokes", "extends_deadline_of", "references", "issued_under")


def _norm(text):
    return " ".join((text or "").split()).lower()


async def offline_model(prompt, **_kwargs):
    """Declines every candidate: only the deterministic stages produce anything."""
    return json.dumps({"items": []})


# ─── Loading ─────────────────────────────────────────────────────────────────


def add_fixture(db, fixture):
    from ingestion.chunking import chunk_pages
    from ingestion.models import Chunk, DocumentAccess, Page, Revision
    from models.database import Document

    doc_id = fixture["id"]
    provenance = {"filename": f"{doc_id}.pdf", "file_type": "pdf", "regulator": "CBN", "doc_type": "regulatory",
                  "classification": "public", "reference_number": fixture.get("reference"),
                  "reference_number_normalized": fixture.get("reference"),
                  "published_date": fixture.get("published_date")}
    db.add(Document(id=doc_id, title=fixture["title"], filename=f"{doc_id}.pdf", file_type="pdf", status="indexed",
                    uploaded_by_id="evaluation-owner", extra_metadata={"pipeline": "v1"}))
    db.add(DocumentAccess(document_id=doc_id, workspace_id="evaluation", shared_regulatory=True))
    db.add(Revision(id=doc_id, source_key=f"fixture:{doc_id}", sha256=doc_id.encode().hex()[:64].ljust(64, "0"),
                    is_current=True, provenance=provenance, review_status="approved", created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    items = []
    for position, text in enumerate(fixture["pages"]):
        db.add(Page(document_id=doc_id, position=position, page_number=position + 1, locator=None,
                    method="pdf_text", raw_text=text, text=text, quality={}))
        items.append({"text": text, "page_number": position + 1, "locator": None})
    for chunk in chunk_pages(items):
        db.add(Chunk(id=f"{doc_id}_chunk_{chunk['chunk_index']}", document_id=doc_id,
                     chunk_index=chunk["chunk_index"], content=chunk["content"],
                     provenance={k: v for k, v in chunk.items() if k not in {"content", "chunk_index"}}))


def claim_one(db, key):
    """Claim this job; every other waiting job is parked for the call."""
    from ingestion.models import Job
    from ingestion.queue import claim

    others = db.query(Job).filter(Job.id != key, Job.state.in_(["queued", "retry"])).all()
    saved = [(job, job.available_at) for job in others]
    for job in others:
        job.available_at = datetime(2999, 1, 1)
    db.query(Job).filter(Job.id == key).update({"available_at": datetime(2000, 1, 1)})
    db.commit()
    lease = claim(db)
    for job, available_at in saved:
        job.available_at = available_at
    db.commit()
    return lease if lease and lease[0] == key else None


async def run_claimed(db, lease, kind, target, complete):
    """As the worker does: the lease is renewed every 30 seconds while the job runs."""
    from ingestion.db import Session
    from ingestion.queue import heartbeat
    from services.compliance_graph.jobs import run_job

    async def renew():
        while True:
            await asyncio.sleep(30)
            try:
                with Session() as other:
                    if not heartbeat(other, lease[0], lease[1]):
                        return
            except Exception:  # SQLite briefly locked by the job's own write: try again next beat
                continue

    pulse = asyncio.create_task(renew())
    try:
        # The production time box (GRAPH_JOB_TIME_BOX_SECONDS): long documents checkpoint and continue.
        await run_job(db, lease[0], lease[1], kind, target, complete=complete)
    finally:
        pulse.cancel()


async def extract(db, document_id, complete):
    """Run graph:{document_id} until it finishes (deferrals for long documents just continue)."""
    from ingestion.models import Job
    from ingestion.queue import enqueue

    enqueue(db, "graph", document_id)
    db.commit()
    key = f"graph:{document_id}"
    outage_waits = 0
    for _slice in range(60):
        lease = claim_one(db, key)
        if lease is None:
            break
        await run_claimed(db, lease, "graph", document_id, complete)
        job = db.get(Job, key)
        db.refresh(job)
        if job.state in {"done", "failed", "cancelled"}:
            return job.state, job.error
        if (job.error or "").startswith("Language model unavailable"):
            # The worker would wait 15 minutes; the eval waits a minute at a time, up to 20 minutes.
            outage_waits += 1
            if outage_waits > 20:
                break
            print(f"    model unavailable; waiting a minute ({outage_waits}/20)", flush=True)
            await asyncio.sleep(60)
        elif (job.error or "").startswith("Daily model budget reached"):
            break
    job = db.get(Job, key)
    return (job.state if job else "missing"), (job.error if job else None)


# ─── Checks ──────────────────────────────────────────────────────────────────


def _target(spec):
    kind, _, value = spec.partition(":")
    if spec == "*":
        return None, None
    to_type = {"doc": "document", "ref": "reference", "act": "act"}[kind]
    return to_type, (None if value == "*" else value)


def _links(db, document_id, relations=None, to=None, basis=None):
    from models.compliance_graph import Link

    query = db.query(Link).filter(Link.from_type == "document", Link.from_id == document_id, Link.status == "active")
    if relations:
        query = query.filter(Link.relation.in_(relations))
    if to:
        to_type, to_id = _target(to)
        if to_type:
            query = query.filter(Link.to_type == to_type)
        if to_id:
            query = query.filter(Link.to_id == to_id)
    if basis:
        query = query.filter(Link.basis == basis)
    return query.all()


def _obligations(db, document_id):
    from models.compliance_graph import Obligation

    return db.query(Obligation).filter(Obligation.document_id == document_id, Obligation.status == "active").all()


def evaluate_check(db, document_id, check, profiles):
    """(passed, detail) for one check."""
    from models.compliance_graph import ChangeEvent, GraphDocument, Link
    from services.compliance_graph import applicability

    gd = db.get(GraphDocument, document_id)
    kind = check["check"]
    if gd is None:
        return False, "the document was never extracted"
    if kind == "reference":
        return gd.reference_number == check["equals"], f"reference is {gd.reference_number}"
    if kind == "letter_date":
        found = (gd.facts or {}).get("letter_date")
        return found == check["equals"], f"letter date is {found}"
    if kind == "role":
        return gd.role == check["equals"], f"role is {gd.role} ({gd.role_basis})"
    if kind in {"addressee", "no_addressee"}:
        links = db.query(Link).filter(Link.relation == "applies_to", Link.from_id == document_id,
                                      Link.status == "active").all()
        found = sorted((link.to_id, link.basis) for link in links)
        if kind == "addressee":
            return (check["code"], check["basis"]) in found, f"addressees are {found}"
        bad = [(c, b) for c, b in found if c in check["codes"] and (not check.get("basis") or b == check["basis"])]
        return not bad, f"addressees are {found}"
    if kind == "applicability":
        links = db.query(Link).filter(Link.relation == "applies_to", Link.from_id == document_id,
                                      Link.status == "active", Link.review_status != "rejected").all()
        state = applicability.evaluate(profiles[check["profile"]], [], None,
                                       [([link.to_id], link.basis, link.review_status) for link in links])
        return state in check["in"], f"{check['profile']}: {state}"
    if kind == "link":
        links = _links(db, document_id, [check["relation"]], check["to"])
        found = sorted({link.basis for link in links})
        ok = bool(links) and (not check.get("basis") or check["basis"] in found)
        return ok, f"{check['relation']} → {check['to']}: {found or 'none'}"
    if kind == "no_link":
        links = _links(db, document_id, check.get("relations") or DOCUMENT_RELATIONS, check.get("to"), check.get("basis"))
        return not links, "found " + ", ".join(f"{l.relation} → {l.to_type}:{l.to_id} ({l.basis})" for l in links) if links else "none"
    if kind == "isolated_from":
        other = check["document"]
        links = db.query(Link).filter(Link.status == "active").filter(
            ((Link.from_document_id == document_id) & ((Link.to_document_id == other) | (Link.to_id == other)))
            | ((Link.from_document_id == other) & ((Link.to_document_id == document_id) | (Link.to_id == document_id)))
        ).all()
        return not links, ", ".join(f"{l.relation} ({l.basis})" for l in links) or "none"
    if kind == "effective":
        found = (gd.effective_date.isoformat() if gd.effective_date else None, gd.effective_basis)
        if check.get("none"):
            return found[0] is None, f"effective {found}"
        return found == (check["date"], check["basis"]), f"effective {found}"
    if kind == "not_effective":
        found = gd.effective_date.isoformat() if gd.effective_date else None
        same = found == check["date"] and (not check.get("basis") or gd.effective_basis == check["basis"])
        return not same, f"effective {found} ({gd.effective_basis})"
    if kind in {"change_event", "no_change_event"}:
        events = db.query(ChangeEvent).filter(ChangeEvent.trigger_document_id == document_id,
                                              ChangeEvent.status == "active").all()
        found = [(e.kind, e.subject_document_id) for e in events]
        if kind == "no_change_event":
            return not events, f"events {found}"
        return (check["kind"], check["subject"]) in found, f"events {found}"
    obligations = _obligations(db, document_id)
    if kind == "requirement_count":
        n = len(obligations)
        return check.get("min", 0) <= n <= check.get("max", 10 ** 6), f"{n} requirement(s)"
    matches = [o for o in obligations if _norm(check["quote"]) in _norm(o.quote)]
    if kind == "no_requirement":
        return not matches, f"extracted: {matches[0].quote[:120]}" if matches else "not extracted"
    if kind == "requirement":
        if not matches:
            return False, "not extracted"
        o = matches[0]
        problems = []
        if check.get("kind") and o.kind != check["kind"]:
            problems.append(f"kind {o.kind}")
        if check.get("deadline"):
            rule = o.deadline_rule or {}
            if any(rule.get(k) != v for k, v in check["deadline"].items()):
                problems.append(f"deadline {rule or None}")
        if check.get("addressee_codes") is not None and sorted(o.addressee_codes or []) != sorted(check["addressee_codes"]):
            problems.append(f"addressees {o.addressee_codes}")
        return not problems, "; ".join(problems) or "extracted"
    raise ValueError(f"Unknown check {kind}")


# ─── Mapping: a pilot workspace's own policy, procedure and records ──────────


def setup_workspace(db, mapping):
    from ingestion.chunking import chunk_pages
    from ingestion.models import Chunk, DocumentAccess, Membership, Page, Revision, Workspace
    from models.compliance_graph import InstitutionProfile
    from models.database import Document, User

    ws = mapping["workspace"]
    db.add(Workspace(id=ws, name="Pilot microfinance bank"))
    db.add(User(id="pilot-admin", email="pilot-admin@example.invalid", full_name="Pilot Admin", role="admin",
                hashed_password="unused"))
    db.add(Membership(user_id="pilot-admin", workspace_id=ws))
    db.add(InstitutionProfile(workspace_id=ws, category_codes=list(mapping["categories"]), basis="confirmed"))
    for spec in mapping["documents"]:
        text = (GOLD.parent / spec["file"]).read_text(encoding="utf-8")
        name = Path(spec["file"]).name
        db.add(Document(id=spec["id"], title=spec["title"], filename=name, file_type="txt", status="indexed",
                        uploaded_by_id="pilot-admin", extra_metadata={"pipeline": "v1", "document_role": spec["role"]}))
        db.add(DocumentAccess(document_id=spec["id"], workspace_id=ws, shared_regulatory=False))
        db.add(Revision(id=spec["id"], source_key=f"pilot:{name}", sha256=spec["id"].encode().hex()[:64].ljust(64, "0"),
                        is_current=True, review_status="approved", created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        provenance={"filename": name, "file_type": "txt", "document_role": spec["role"]}))
        db.add(Page(document_id=spec["id"], position=0, page_number=1, locator=None, method="text", raw_text=text,
                    text=text, quality={}))
        for chunk in chunk_pages([{"text": text, "page_number": 1, "locator": None}]):
            db.add(Chunk(id=f"{spec['id']}_chunk_{chunk['chunk_index']}", document_id=spec["id"],
                         chunk_index=chunk["chunk_index"], content=chunk["content"],
                         provenance={k: v for k, v in chunk.items() if k not in {"content", "chunk_index"}}))
    db.commit()


async def sync_workspace(db, workspace, complete):
    """Run graph_ws:{workspace} until it settles (a run may ask for one more)."""
    from ingestion.models import Job
    from ingestion.queue import enqueue

    enqueue(db, "graph_ws", workspace)
    db.commit()
    key = f"graph_ws:{workspace}"
    for _run in range(10):
        lease = claim_one(db, key)
        if lease is None:
            break
        await run_claimed(db, lease, "graph_ws", workspace, complete)
    job = db.get(Job, key)
    db.refresh(job)
    return job.state, job.error


def _controls(db, workspace, quote, document=None):
    from models.compliance_graph import Control

    query = db.query(Control).filter(Control.workspace_id == workspace, Control.status == "active")
    if document:
        query = query.filter(Control.document_id == document)
    return [c for c in query.all() if _norm(quote) in _norm(c.quote or c.name)]


def _lineages(db, requirement):
    return {o.lineage_id for o in _obligations(db, requirement["document"]) if _norm(requirement["quote"]) in _norm(o.quote)}


def evaluate_mapping_check(db, workspace, check):
    from models.compliance_graph import Link

    kind = check["check"]
    if kind in {"control", "not_control"}:
        found = _controls(db, workspace, check["quote"], check["document"])
        detail = "; ".join(c.name for c in found) or "none"
        return (bool(found) if kind == "control" else not found), detail
    links = db.query(Link).filter(Link.workspace_id == workspace, Link.status == "active",
                                  Link.review_status != "rejected")
    if kind in {"maps", "no_map"}:
        controls = _controls(db, workspace, check["control"])
        if not controls:
            return kind == "no_map", "control not extracted"
        mapped = links.filter(Link.relation == "addresses", Link.from_type == "control",
                              Link.from_id.in_([c.id for c in controls])).all()
        described = "; ".join(f"{(l.attributes or {}).get('coverage')}: {l.to_id[:12]}" for l in mapped) or "no links"
        if kind == "no_map":
            return not mapped, described
        lineages = _lineages(db, check["requirement"])
        if not lineages:
            return False, "requirement not extracted"
        return any(l.to_id in lineages for l in mapped), described
    rows = links.filter(Link.relation == "evidences", Link.from_id == check["document"]).all()
    described = "; ".join(f"{l.to_type}:{l.to_id[:12]}" for l in rows) or "no links"
    if kind == "no_evidences":
        ids = {c.id for c in _controls(db, workspace, check["control"])}
        return not any(l.to_type == "control" and l.to_id in ids for l in rows), described
    for option in check["any_of"]:
        if "control" in option:
            ids = {c.id for c in _controls(db, workspace, option["control"])}
            if any(l.to_type == "control" and l.to_id in ids for l in rows):
                return True, described
        elif any(l.to_type == "obligation" and l.to_id in _lineages(db, option["requirement"]) for l in rows):
            return True, described
    return False, described


def confirm_expected(db, scope, mapping) -> int:
    """The pilot admin confirms the suggestions the gold set expects, as a careful reviewer would."""
    from models.compliance_graph import Link
    from services.compliance_graph import review

    ws = mapping["workspace"]
    proposed = db.query(Link).filter(Link.workspace_id == ws, Link.status == "active", Link.review_status == "proposed")
    chosen = set()
    for check in mapping["checks"]:
        if check["check"] == "maps":
            controls = {c.id for c in _controls(db, ws, check["control"])}
            lineages = _lineages(db, check["requirement"])
            chosen |= {l.id for l in proposed.filter(Link.relation == "addresses").all()
                       if l.from_id in controls and l.to_id in lineages}
        elif check["check"] == "evidences":
            for option in check["any_of"]:
                if "control" in option:
                    targets = {c.id for c in _controls(db, ws, option["control"])}
                else:
                    targets = _lineages(db, option["requirement"])
                chosen |= {l.id for l in proposed.filter(Link.relation == "evidences",
                                                         Link.from_id == check["document"]).all() if l.to_id in targets}
    for link_id in sorted(chosen):
        review.review_link(db, scope, link_id, "confirm")
    db.commit()
    return len(chosen)


async def chat_phase(db, gold, complete):
    """The pilot's questions, asked through the real chat agent after a review and a later change."""
    import services.regulatory_research as research
    from agents.strategist import StrategistAgent
    from evaluate_conversations import check_turn
    from ingestion.access import as_user
    from models.database import User
    from services.compliance_graph import review
    from services.compliance_graph.visibility import for_user

    chat, mapping = gold["chat"], gold["mapping"]
    user = db.get(User, "pilot-admin")
    scope = for_user(db, user)
    confirmed = confirm_expected(db, scope, mapping)
    for document_id in chat["owner"]["documents"]:
        for lineage in sorted({o.lineage_id for o in _obligations(db, document_id)}):
            review.set_requirement_status(db, scope, lineage, {"owner_team": chat["owner"]["team"]})
    db.commit()
    # A change arrives after the review: it must flag the confirmed mappings it touches.
    add_fixture(db, chat["change"])
    db.commit()
    await extract(db, chat["change"]["id"], complete)
    await sync_workspace(db, mapping["workspace"], complete)
    research.eligible = lambda _question: False  # the library and the graph only, no live web research

    def unavailable(_question, _context):
        raise RuntimeError("compliance graph unavailable (simulated)")

    rows = []
    for turn in chat["turns"]:
        agent = StrategistAgent()
        agent.graph_timeout = 10
        if turn.get("graph_outage"):
            agent.graph_step = unavailable
        with as_user(user):
            result = json.loads(await agent.investigate(turn["question"]))
        failures, intent = check_turn(turn, result)
        records = [c for c in result.get("citations", [])
                   if (c.get("provenance") or {}).get("source_kind") == "iroko_record"]
        if turn.get("graph_trace") and not any(s.get("tool") == "graph" for s in result.get("agent_trace", [])):
            failures.append("the graph step did not run")
        if len(records) < turn.get("record_citations_min", 0):
            failures.append(f"{len(records)} record citation(s), expected at least {turn['record_citations_min']}")
        if "record_citations_max" in turn and len(records) > turn["record_citations_max"]:
            failures.append(f"{len(records)} record citation(s), expected at most {turn['record_citations_max']}")
        rows.append({"id": turn["id"], "question": turn["question"], "intent": intent, "passed": not failures,
                     "failures": failures, "status": result.get("answer_status"), "answer": result.get("answer"),
                     "citations": [c.get("document_title") for c in result.get("citations", [])],
                     "graph": [s.get("description") for s in result.get("agent_trace", []) if s.get("tool") == "graph"]})
        print(f"[chat] {turn['id']}: {'pass' if not failures else 'FAIL ' + '; '.join(failures)}", flush=True)
    return {"confirmed_links": confirmed, "turns": rows}


def mapping_listing(db, workspace):
    """Every suggestion, in words, for a person to read."""
    from models.compliance_graph import Control, Link, Obligation

    out = []
    for link in db.query(Link).filter(Link.workspace_id == workspace, Link.status == "active",
                                      Link.relation.in_(["addresses", "evidences"])):
        source = (db.get(Control, link.from_id).quote if link.from_type == "control" else link.from_id)
        if link.to_type == "control":
            target = db.get(Control, link.to_id).quote
        else:
            row = db.query(Obligation).filter(Obligation.lineage_id == link.to_id, Obligation.status == "active").first()
            target = row.quote if row else link.to_id
        out.append({"relation": link.relation, "from": source, "to": target, "basis": link.basis,
                    "coverage": (link.attributes or {}).get("coverage"), "rationale": link.rationale})
    return out


# ─── Run ─────────────────────────────────────────────────────────────────────


async def run(args):
    from evaluate_document_answers import ARTIFACTS, save, setup_local

    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    cases = gold["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
        if len(cases) != len(set(args.case)):
            raise SystemExit("Unknown or duplicate --case")
    corpus = json.loads((ARTIFACTS / "corpus.json").read_text(encoding="utf-8"))
    run_dir = Path(tempfile.mkdtemp(prefix="graph-", dir=ARTIFACTS))
    SessionLocal = setup_local(corpus, run_dir)
    from ingestion.models import DocumentAccess
    from models.compliance_graph import GraphRun

    wanted = {c["document"] for c in cases}
    # A citation's target must be in the library for the check to mean anything: load everything,
    # extract what the selected cases need plus anything they point at.
    with SessionLocal() as db:
        for access in db.query(DocumentAccess).all():
            access.shared_regulatory = True  # CBN instruments are the shared library
        for fixture in gold.get("fixtures", []):
            add_fixture(db, fixture)
        db.commit()
    order = sorted(corpus["documents"], key=lambda d: (d.get("created_at") or "", d["id"]))
    documents = [d["id"] for d in order] + [f["id"] for f in gold.get("fixtures", [])]
    if args.case:
        targets = {t.split(":", 1)[1] for c in cases for chk in c["checks"]
                   for t in [chk.get("to", ""), "doc:" + chk.get("document", "") if chk.get("document") else ""]
                   if t.startswith("doc:") and not t.endswith("*")}
        targets |= {chk["subject"] for c in cases for chk in c["checks"] if chk.get("subject")}
        documents = [d for d in documents if d in wanted | targets]
        # The shared-reference fixture needs both carriers of its reference in the library.
        if "fixture-cites-shared-reference" in wanted:
            documents += [d for d in ("f1a2c7f3-d13e-4a95-9ae9-7d6817e1eeec", "17df5c74-d087-4511-be95-7f6eb978f622")
                          if d not in documents]
    complete = offline_model if args.offline else None
    started = time.monotonic()
    states = {}
    with SessionLocal() as db:
        for number, document_id in enumerate(documents, 1):
            t0 = time.monotonic()
            state, error = await extract(db, document_id, complete)
            states[document_id] = {"state": state, "error": error, "seconds": round(time.monotonic() - t0, 1)}
            print(f"[{number}/{len(documents)}] {document_id[:36]} {state} {states[document_id]['seconds']}s", flush=True)

        results, totals = [], {"deterministic": [0, 0], "model": [0, 0]}
        for case in cases:
            rows = []
            for check in case["checks"]:
                model_check = bool(check.get("model"))
                if model_check and args.offline:
                    continue
                passed, detail = evaluate_check(db, case["document"], check, gold["profiles"])
                bucket = totals["model" if model_check else "deterministic"]
                bucket[0] += passed
                bucket[1] += 1
                rows.append({"check": check, "passed": passed, "detail": detail})
            extracted = [{"quote": o.quote, "kind": o.kind, "summary": o.summary, "deadline": o.deadline_rule,
                          "addressees": o.addressee_codes, "basis": o.addressee_basis}
                         for o in sorted(_obligations(db, case["document"]), key=lambda o: o.position or 0)]
            results.append({"id": case["id"], "document": case["document"], "checks": rows,
                            "failed": sum(not r["passed"] for r in rows), "requirements": extracted})
        mapping_rows, suggestions = [], []
        if args.mapping:
            mapping = gold["mapping"]
            setup_workspace(db, mapping)
            for spec in mapping["documents"]:
                state, error = await extract(db, spec["id"], complete)
                states[spec["id"]] = {"state": state, "error": error}
                print(f"[workspace] {spec['id']} {state}", flush=True)
            states["graph_ws"] = dict(zip(("state", "error"), await sync_workspace(db, mapping["workspace"], complete)))
            for check in mapping["checks"]:
                passed, detail = evaluate_mapping_check(db, mapping["workspace"], check)
                mapping_rows.append({"check": check, "passed": passed, "detail": detail})
            suggestions = mapping_listing(db, mapping["workspace"])
            results.append({"id": "mapping", "document": mapping["workspace"], "checks": mapping_rows,
                            "failed": sum(not r["passed"] for r in mapping_rows), "requirements": []})
        chat_result = await chat_phase(db, gold, complete) if args.chat else None
        recall_rows = [r for c in results for r in c["checks"] if r["check"]["check"] == "requirement"]
        trap_rows = [r for c in results for r in c["checks"] if r["check"]["check"] == "no_requirement"]
        tokens = sum(run.tokens_estimated or 0 for run in db.query(GraphRun).filter(GraphRun.stage == "document"))
        report = {
            "mode": "offline" if args.offline else args.model,
            "documents": len(documents),
            "extraction": states,
            "deterministic_passed": f"{totals['deterministic'][0]}/{totals['deterministic'][1]}",
            "model_passed": None if args.offline else f"{totals['model'][0]}/{totals['model'][1]}",
            "requirement_recall": None if args.offline or not recall_rows else
                round(sum(r["passed"] for r in recall_rows) / len(recall_rows), 3),
            "precision_traps_avoided": None if args.offline or not trap_rows else
                f"{sum(r['passed'] for r in trap_rows)}/{len(trap_rows)}",
            "mapping_passed": f"{sum(r['passed'] for r in mapping_rows)}/{len(mapping_rows)}" if args.mapping else None,
            "chat_passed": (f"{sum(t['passed'] for t in chat_result['turns'])}/{len(chat_result['turns'])}"
                            if chat_result else None),
            "estimated_tokens": tokens,
            "seconds": round(time.monotonic() - started, 1),
            "cases": results,
            "suggestions": suggestions,
            "chat": chat_result,
        }
    out = ARTIFACTS / f"graph-extraction-{datetime.now():%Y%m%d-%H%M%S}.json"
    save(out, report)
    for case in results:
        for row in case["checks"]:
            if not row["passed"]:
                spec = {k: v for k, v in row["check"].items() if k not in ("why",)}
                print(f"FAIL {case['id']}: {json.dumps(spec, ensure_ascii=False)} -> {row['detail']}")
    print(json.dumps({k: report[k] for k in ("mode", "documents", "deterministic_passed", "model_passed",
                                             "requirement_recall", "precision_traps_avoided", "mapping_passed",
                                             "chat_passed", "estimated_tokens", "seconds")}, indent=1))
    print(json.dumps({"report": str(out)}))
    failed_jobs = [d for d, s in states.items() if s["state"] != "done"]
    if failed_jobs:
        print("Jobs that did not finish:", failed_jobs)
    chat_failed = bool(chat_result) and not all(t["passed"] for t in chat_result["turns"])
    return 1 if any(c["failed"] for c in results) or failed_jobs or chat_failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="No model: check only the deterministic stages")
    parser.add_argument("--case", action="append", default=[], help="Run only these case ids")
    parser.add_argument("--model", choices=["nano", "sol"], default="nano",
                        help="nano: the Chat Completions test deployment; sol: production's Responses model, "
                             "run as the worker runs it (no fallback)")
    parser.add_argument("--tpm", type=int, default=0,
                        help="Graph token pacing per minute (default: 90000 for nano, 40000 for sol, which "
                             "shares its quota with live chat)")
    parser.add_argument("--mapping", action="store_true",
                        help="Also run the pilot workspace: controls, evidence and mapping suggestions")
    parser.add_argument("--chat", action="store_true",
                        help="After --mapping: confirm the expected links, add a later change, and ask the pilot's "
                             "questions through the real chat agent (reads the shared search index)")
    args = parser.parse_args()
    if args.mapping and (args.offline or args.case):
        parser.error("--mapping needs the model and the whole library (no --offline, no --case)")
    if args.chat and not args.mapping:
        parser.error("--chat needs --mapping")
    logging.disable(logging.CRITICAL)
    if not args.offline:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / ".env", override=True)
        if args.model == "nano":
            # The nano Chat Completions test deployment, never the primary model.
            os.environ["AZURE_OPENAI_RESPONSES_ENDPOINT"] = ""
            os.environ["AZURE_OPENAI_RESPONSES_API_KEY"] = ""
            if os.getenv("AZURE_OPENAI_DEPLOYMENT") != "gpt-5.4-nano":
                parser.error("--model nano requires AZURE_OPENAI_DEPLOYMENT=gpt-5.4-nano")
        else:
            # As the worker runs it: the Responses primary only; an outage defers instead of downgrading.
            if not (os.getenv("AZURE_OPENAI_RESPONSES_ENDPOINT") and os.getenv("AZURE_OPENAI_RESPONSES_API_KEY")):
                parser.error("--model sol needs AZURE_OPENAI_RESPONSES_ENDPOINT and _API_KEY in backend/.env")
            os.environ["LLM_FALLBACK"] = "false"
        args.tpm = args.tpm or (90000 if args.model == "nano" else 40000)
    os.environ["COMPLIANCE_GRAPH_ENABLED"] = "true"
    os.environ["GRAPH_TOKENS_PER_MINUTE"] = "0" if args.offline else str(max(1000, args.tpm))
    os.environ.setdefault("GRAPH_DAILY_TOKEN_BUDGET", "3000000")
    os.environ.setdefault("GRAPH_WORKSPACE_DAILY_TOKEN_BUDGET", "3000000")
    # setup_local points DATABASE_URL at the run's own SQLite file before any app module is imported.
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
