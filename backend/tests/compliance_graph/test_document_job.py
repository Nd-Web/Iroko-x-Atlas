"""The graph:{document} job end to end, on isolated SQLite with a fake model."""

import contextlib
import subprocess
import sys
from datetime import date
from pathlib import Path

from ingestion.models import Job, Page
from models.compliance_graph import ChangeEvent, Control, GraphDocument, Link, Obligation
from services.compliance_graph.jobs import backfill, run_job
from tests.compliance_graph import factory as f

BACKEND = Path(__file__).resolve().parents[2]


async def extract(db, document_id, model=None, **kw):
    key, token = f.claim_job(db, "graph", document_id)
    await run_job(db, key, token, "graph", document_id, complete=model or f.FakeModel(), **kw)
    return db.get(Job, key)


def active_obligations(db, document_id):
    return (db.query(Obligation).filter(Obligation.document_id == document_id, Obligation.status == "active")
            .order_by(Obligation.position).all())


async def test_regulation_extraction_end_to_end(db):
    f.document(db, "bvn", title="BVN Enrollment for OFIs Customers", pages=[f.BVN_LETTER], workspace="ws-lib",
               shared=True, regulator="CBN", reference="OFI/DIR/CIR/GEN/17/139", published="2017-04-21")
    job = await extract(db, "bvn")
    assert job.state == "done"
    gd = db.get(GraphDocument, "bvn")
    assert (gd.role, gd.role_basis, gd.extraction_status) == ("regulation", "stated", "done")
    obligations = active_obligations(db, "bvn")
    page_text = db.query(Page).filter_by(document_id="bvn").one().text
    assert len(obligations) == 3
    for o in obligations:
        assert page_text[o.page_char_start:o.page_char_end].split() == o.quote.split()
        assert o.chunk_id and o.lineage_id == o.id
    returns = next(o for o in obligations if "monthly returns" in o.quote)
    assert returns.deadline_rule["kind"] == "monthly_day" and returns.deadline_rule["day"] == 10
    assert next(o for o in obligations if "shall not open" in o.quote).kind == "prohibition"
    applies = db.query(Link).filter(Link.relation == "applies_to", Link.from_id == "bvn").one()
    assert (applies.to_id, applies.basis, applies.review_status) == ("ofi", "stated", "proposed")
    # "Effective August 1, 2017, OFIs shall not open accounts ..." dates that requirement, not the circular.
    assert gd.effective_date is None and gd.effective_basis is None
    assert gd.facts["letter_date"] == "2017-04-21"


async def test_rerun_is_idempotent_and_never_overwrites_a_review(db):
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139")
    await extract(db, "bvn")
    first = {o.id for o in active_obligations(db, "bvn")}
    reviewed = active_obligations(db, "bvn")[0]
    reviewed.review_status, reviewed.summary = "confirmed", "Edited by the reviewer"
    db.commit()
    assert backfill(db, document_id="bvn", force=True) == 1
    key, token = f.claim_key(db, "graph:bvn")
    await run_job(db, key, token, "graph", "bvn", complete=f.FakeModel())
    again = active_obligations(db, "bvn")
    assert {o.id for o in again} == first
    kept = db.get(Obligation, reviewed.id)
    assert kept.summary == "Edited by the reviewer" and kept.review_status == "confirmed"
    assert kept.proposal and kept.proposal["summary"] != "Edited by the reviewer"
    assert db.query(Link).filter(Link.relation == "applies_to").count() == 1


async def test_references_resolve_in_either_order_and_extension_is_stated(db):
    f.document(db, "ext", title="BVN timeline extension", pages=[f.EXTENSION_LETTER], workspace="ws-lib",
               shared=True, regulator="CBN", reference="OFI/DIR/CIR/GEN/18/011")
    await extract(db, "ext")
    pending = db.query(Link).filter(Link.from_id == "ext", Link.to_type == "reference", Link.status == "active").all()
    assert {(link.relation, link.basis) for link in pending} == {("references", "stated"),
                                                                ("extends_deadline_of", "stated")}
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139")
    await extract(db, "bvn")
    resolved = db.query(Link).filter(Link.from_id == "ext", Link.to_type == "document", Link.status == "active").all()
    assert {(link.relation, link.to_id) for link in resolved} == {("references", "bvn"), ("extends_deadline_of", "bvn")}
    assert not db.query(Link).filter(Link.to_type == "reference", Link.status == "active").count()


SEPARATE_EXTENSION = """CENTRAL BANK OF NIGERIA

Ref: OFI/DIR/CIR/GEN/18/011

August 1, 2017

LETTER TO OTHER FINANCIAL INSTITUTIONS (OFIs)

Your attention is drawn to our letter on the above subject referenced: OFI/DIR/CIR/GEN/17/139
dated April 21, 2017 in which all OFIs were required to enroll their customers.

In this regard, Management has approved an extension of the timeline to December 31, 2017.
"""


async def test_a_change_stated_apart_from_the_citation_is_only_suggested(db):
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139")
    await extract(db, "bvn")
    f.document(db, "ext", title="BVN Enrollment - Extension of Timeline", pages=[SEPARATE_EXTENSION],
               workspace="ws-lib", shared=True, regulator="CBN", reference="OFI/DIR/CIR/GEN/18/011")
    model = f.FakeModel(relation="extends_deadline_of")
    await extract(db, "ext", model)
    asked = next(c["payload"] for c in model.calls if "items" in c["payload"] and "instrument" in c["payload"])
    assert any("extension of the timeline" in s for s in asked["instrument"]["change_sentences"])
    links = {(link.relation, link.to_id, link.basis)
             for link in db.query(Link).filter(Link.from_id == "ext", Link.status == "active", Link.to_type == "document")}
    assert links == {("references", "bvn", "stated"), ("extends_deadline_of", "bvn", "suggested")}
    # Only a stated (or confirmed) change is a library change event.
    assert not db.query(ChangeEvent).filter(ChangeEvent.trigger_document_id == "ext").count()
    gd = db.get(GraphDocument, "ext")
    assert gd.effective_date is None  # nothing in the letter says when IT takes effect


async def test_deadline_counted_from_the_letter_date_is_a_date(db):
    letter = ("CENTRAL BANK OF NIGERIA\n\nOFI/DOA/CON/OFI/001/304\n\nJanuary 09, 2023\n\n"
              "# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS\n\n"
              "In addition, any existing placement(s) in such entities by any OFI must be liquidated\n"
              "within 90 days of the date of this letter.\n")
    f.document(db, "divest", title="Prohibition of placements", pages=[letter], workspace="ws-lib", shared=True,
               regulator="CBN", reference="OFI/DOA/CON/OFI/001/304")
    await extract(db, "divest")
    [obligation] = active_obligations(db, "divest")
    assert obligation.deadline_rule["kind"] == "fixed_date"
    assert obligation.deadline_rule["date"] == "2023-04-09" and obligation.deadline_rule["from"] == "letter_date"


async def test_list_items_are_requirements_with_their_introductions_subject(db):
    from tests.compliance_graph.test_rules import LIST_LETTER

    f.document(db, "lists", title="BVN and SPV duties", pages=[LIST_LETTER], workspace="ws-lib", shared=True,
               regulator="CBN", reference="OFI/DIR/CIR/GEN/17/140")
    await extract(db, "lists")
    by_quote = {o.quote: o for o in active_obligations(db, "lists")}
    assert not any(q.endswith("required to:") for q in by_quote)  # introductions carry no duty of their own
    display = by_quote["b. Conspicuously display notices sensitizing customers on BVN in the banking hall"]
    assert (display.addressee_codes, display.addressee_basis, display.addressee_span) == (["ofi"], "stated", "OFIs")
    spv = next(o for q, o in by_quote.items() if "Submit returns on all SPVs" in q)
    assert (spv.addressee_codes, spv.addressee_basis) == (["dfi"], "stated")


CITES_SHARED = ("CENTRAL BANK OF NIGERIA\n\nRef: OFI/DIR/DOC/GEN/021/010\n\nJanuary 15, 2020\n\n"
                "# LETTER TO ALL MICROFINANCE BANKS (MFBs)\n\nFurther to our letter referenced OFI/DIR/DOC/GEN/020/252 on "
                "the revised targets, all MFBs are required to render the monthly report.\n")


# A letter and its template carry the same reference; a third letter cites it.
SHARED_REFERENCE_DOCS = {
    "letter": dict(title="Inclusion targets letter", reference="OFI/DIR/DOC/GEN/020/252",
                   pages=["Ref: OFI/DIR/DOC/GEN/020/252\n\nJune 20, 2019\n\n# LETTER TO ALL MFBs\n\nBody of the letter.\n"]),
    "template": dict(title="Inclusion data template", reference="OFI/DIR/DOC/GEN/020/252",
                     pages=["CENTRAL BANK OF NIGERIA\nDATA TEMPLATE\nState totals"]),
    "cites": dict(title="Inclusion returns letter", reference="OFI/DIR/DOC/GEN/021/010", pages=[CITES_SHARED]),
}


async def test_a_shared_reference_resolves_the_same_in_any_order(db):
    results = []
    for order in (["cites", "letter", "template"], ["letter", "cites", "template"], ["letter", "template", "cites"]):
        for model in (Link, ChangeEvent, Obligation, GraphDocument):
            db.query(model).delete()  # earlier rounds' documents leave the graph
        db.commit()
        suffix = "-".join(order)
        for name in order:
            f.document(db, f"{name}-{suffix}", workspace="ws-lib", shared=True, regulator="CBN",
                       **SHARED_REFERENCE_DOCS[name])
            await extract(db, f"{name}-{suffix}")
        links = db.query(Link).filter(Link.from_id == f"cites-{suffix}", Link.relation == "references",
                                      Link.status == "active").all()
        results.append(sorted((link.to_id.split("-")[0], link.basis) for link in links))
    assert results == [[("letter", "suggested"), ("template", "suggested")]] * 3


async def test_a_change_resolved_after_the_fact_is_still_a_library_change_event(db):
    f.document(db, "amend", title="BVN amendment", pages=[f.AMENDING_LETTER], workspace="ws-lib", shared=True,
               regulator="CBN", reference="OFI/DIR/CIR/GEN/19/001")
    await extract(db, "amend")
    assert not db.query(ChangeEvent).count()  # the amended circular is not in the library yet
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139")
    await extract(db, "bvn")
    amends = db.query(Link).filter(Link.relation == "amends", Link.status == "active").one()
    assert (amends.to_type, amends.to_id, amends.basis) == ("document", "bvn", "stated")
    event = db.query(ChangeEvent).one()
    assert (event.kind, event.subject_document_id, event.trigger_document_id) == ("amended_by", "bvn", "amend")


async def test_stated_change_becomes_a_library_change_event(db):
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139")
    await extract(db, "bvn")
    f.document(db, "amend", title="BVN amendment", pages=[f.AMENDING_LETTER], workspace="ws-lib", shared=True,
               regulator="CBN", reference="OFI/DIR/CIR/GEN/19/001")
    await extract(db, "amend")
    amends = db.query(Link).filter(Link.relation == "amends").one()
    assert (amends.from_id, amends.to_id, amends.basis) == ("amend", "bvn", "stated")
    event = db.query(ChangeEvent).filter(ChangeEvent.kind == "amended_by").one()
    assert event.subject_document_id == "bvn" and event.trigger_document_id == "amend"
    mlpa = db.query(Link).filter(Link.to_type == "act", Link.to_id == "mlpa_2011").one()
    assert mlpa.relation == "references"
    applies = {link.to_id for link in db.query(Link).filter(Link.relation == "applies_to", Link.from_id == "amend")}
    assert applies == {"mfb"}


async def test_private_documents_of_two_workspaces_are_never_linked(db):
    f.document(db, "a-copy", title="BVN (A's private copy)", pages=[f.BVN_LETTER], workspace="ws-a",
               regulator="CBN", reference="OFI/DIR/CIR/GEN/17/139")
    await extract(db, "a-copy")
    f.document(db, "b-amend", title="B's amendment copy", pages=[f.AMENDING_LETTER], workspace="ws-b",
               regulator="CBN", reference="OFI/DIR/CIR/GEN/19/001")
    await extract(db, "b-amend")
    assert not db.query(Link).filter(Link.to_id == "a-copy").count()
    external = db.query(Link).filter(Link.from_id == "b-amend", Link.relation == "amends").one()
    assert external.to_type == "reference" and external.to_document_id is None


async def test_new_version_keeps_lineage_and_reports_changes(db):
    f.document(db, "v1", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139", source_key="regulator:CBN:bvn")
    await extract(db, "v1")
    v1 = {o.quote: o for o in active_obligations(db, "v1")}
    revised = (f.BVN_LETTER
               .replace("not later\nthan the 10th day", "not later\nthan the 15th day")
               .replace("Effective August 1, 2017, OFIs shall not open accounts for customers without\na BVN.\n",
                        "OFIs must retain BVN records for five years.\n"))
    f.supersede(db, "v1")
    f.document(db, "v2", title="BVN", pages=[revised], workspace="ws-lib", shared=True, regulator="CBN",
               reference="OFI/DIR/CIR/GEN/17/139", source_key="regulator:CBN:bvn", previous_id="v1")
    await extract(db, "v2")
    v2 = active_obligations(db, "v2")
    unchanged = next(o for o in v2 if "every customer account" in o.quote)
    assert unchanged.lineage_id == v1[unchanged.quote].lineage_id
    reworded = next(o for o in v2 if "15th day" in o.quote)
    assert reworded.lineage_id == next(o for q, o in v1.items() if "10th day" in q).lineage_id
    added = next(o for o in v2 if "five years" in o.quote)
    assert added.lineage_id == added.id
    event = db.query(ChangeEvent).filter(ChangeEvent.kind == "new_version").one()
    assert len(event.details["modified"]) == 1 and len(event.details["removed"]) == 1
    assert event.details["added"] == [added.lineage_id]


async def test_budget_exhaustion_defers_without_spending_an_attempt(db, monkeypatch):
    monkeypatch.setenv("GRAPH_DAILY_TOKEN_BUDGET", "10")
    f.document(db, "pol", title="AML policy", pages=[f.AML_POLICY], role="policy")
    model = f.FakeModel(role="policy")
    job = await extract(db, "pol", model)
    assert (job.state, job.attempts) == ("retry", 0)
    assert job.available_at > job.updated_at or job.available_at.date() >= date.today()
    assert not model.calls
    assert db.get(GraphDocument, "pol").extraction_status == "deferred"


async def test_model_outage_defers_and_never_falls_back(db):
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN")
    job = await extract(db, "bvn", f.FakeModel(fail=RuntimeError("LLM call failed after 3 retries")))
    assert (job.state, job.attempts) == ("retry", 0)
    gd = db.get(GraphDocument, "bvn")
    assert "unavailable" in gd.error and gd.stage_state.get("outage_since")


async def test_malformed_replies_shrink_the_batch_and_never_fail(db):
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN")
    job = await extract(db, "bvn", f.FakeModel(broken=1))
    assert job.state == "done" and len(active_obligations(db, "bvn")) == 3
    f.document(db, "bvn2", title="BVN 2", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN")
    job = await extract(db, "bvn2", f.FakeModel(broken=100))
    assert job.state == "done" and not active_obligations(db, "bvn2")


async def test_time_box_yields_and_resumes_where_it_stopped(db):
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN")
    job = await extract(db, "bvn", seconds=1e-9)
    assert (job.state, job.attempts) == ("retry", 0)
    assert "role" in db.get(GraphDocument, "bvn").stage_state["done"]
    key, token = f.claim_key(db, "graph:bvn")
    await run_job(db, key, token, "graph", "bvn", complete=f.FakeModel())
    assert db.get(Job, key).state == "done" and len(active_obligations(db, "bvn")) == 3


async def test_disabled_worker_defers_graph_jobs(db, monkeypatch):
    monkeypatch.setenv("COMPLIANCE_GRAPH_ENABLED", "false")
    f.document(db, "bvn", title="BVN", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True, regulator="CBN")
    job = await extract(db, "bvn")
    assert (job.state, job.attempts) == ("retry", 0) and "disabled" in job.error


async def test_controls_survive_a_policy_update(db):
    f.document(db, "pol1", title="AML/CFT Policy", pages=[f.AML_POLICY], role="policy", source_key="upload:u:aml")
    await extract(db, "pol1", f.FakeModel(role="policy"))
    controls = db.query(Control).filter(Control.status == "active").order_by(Control.name).all()
    assert [c.name for c in controls] == ["BVN review before activation", "Monthly BVN exception reconciliation"]
    assert {c.performer_span for c in controls} == {"The Compliance Officer", "The Head of Operations"}
    review = next(c for c in controls if c.name.startswith("BVN review"))
    review.review_status, review.owner_user_id = "confirmed", "owner-1"
    reconcile = next(c for c in controls if c.name.startswith("Monthly"))
    db.commit()
    updated = f.AML_POLICY.replace("reconcile BVN exceptions monthly", "reconcile all BVN exceptions monthly")
    f.supersede(db, "pol1")
    f.document(db, "pol2", title="AML/CFT Policy v2", pages=[updated], role="policy", source_key="upload:u:aml",
               previous_id="pol1")
    await extract(db, "pol2", f.FakeModel(role="policy"))
    kept = db.get(Control, review.id)
    assert kept.document_id == "pol2" and kept.owner_user_id == "owner-1" and kept.review_status == "confirmed"
    reworded = db.get(Control, reconcile.id)
    assert reworded is not None and reworded.document_id == "pol2" and "all BVN exceptions" in reworded.quote
    assert reworded.anchor_history and reworded.anchor_history[-1]["document_id"] == "pol1"
    assert db.query(Control).filter(Control.status == "active").count() == 2


async def test_evidence_record_facts(db):
    f.document(db, "reg", title="Training register Q1 2026", pages=[f.TRAINING_REGISTER], role="evidence_record")
    await extract(db, "reg", f.FakeModel(role="evidence_record"))
    facts = db.get(GraphDocument, "reg").facts["evidence"]
    assert (facts["period_start"], facts["period_end"], facts["record_date"]) == ("2026-01-01", "2026-03-31", "2026-03-20")
    assert facts["activity_span"] == "completed the BVN and KYC refresher training"


async def test_uploader_role_is_kept_and_a_disagreement_is_surfaced(db):
    f.document(db, "doc", title="Q1 register", pages=[f.TRAINING_REGISTER], role="policy")
    await extract(db, "doc", f.FakeModel(role="evidence_record"))
    gd = db.get(GraphDocument, "doc")
    assert (gd.role, gd.role_basis, gd.role_suggestion) == ("policy", "uploader", "evidence_record")


def test_graph_jobs_never_block_or_fail_document_drains(db, monkeypatch):
    from ingestion import batch

    db.add(Job(id="graph:x", kind="graph", target_id="x", state="failed", attempts=5))
    db.add(Job(id="graph_ws:w", kind="graph_ws", target_id="w", state="queued", attempts=0))
    db.commit()
    monkeypatch.setattr(batch, "Session", lambda: contextlib.nullcontext(db))
    pending, failures, _results = batch._status(f.tick(), {})
    assert pending == 0 and failures == []


def test_graph_modules_import_without_fastapi():
    code = ("import sys; sys.modules['fastapi'] = None; "
            "import services.compliance_graph.jobs, services.compliance_graph.extract, "
            "services.compliance_graph.relations, services.compliance_graph.permissions, "
            "services.compliance_graph.visibility, services.compliance_graph.triggers; print('ok')")
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True,
                            env={"PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
                                 "DATABASE_URL": "sqlite://"})
    assert result.returncode == 0, result.stderr[-2000:]
