"""The graph in chat: routing, records answers, bounded expansion, record citations end to end."""

import contextlib
import json

import pytest

from ingestion.access import Principal, as_user
from models.compliance_graph import Link, Obligation
from services.chat_router import heuristic_route, records_kinds
from services.compliance_graph import chat, review, wording
from services.compliance_graph.visibility import for_user
from tests.compliance_graph import factory as f
from tests.compliance_graph.test_workspace import extract, sync

FIVE = {
    "How does this circular relate to our onboarding policy?": None,
    "This requirement changed. Which controls need reviewing?": ["re_review"],
    "The BVN enrolment requirement changed. Which of our controls need reviewing?": ["re_review"],
    "Which requirements don't have supporting evidence in our records?": ["gaps"],
    "Who owns this obligation, and what is due next?": ["owners", "due"],
    "Show the requirement, our control, its evidence and the review history.": ["trace"],
}


def test_the_five_questions_route_as_designed():
    for question, kinds in FIVE.items():
        routed = heuristic_route(question)
        if kinds is None:
            assert routed["intent"] != "compliance_records", question
        else:
            assert routed["intent"] == "compliance_records", question
            assert routed["records_kinds"] == kinds, question


def test_records_intent_is_off_when_the_graph_is_disabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_GRAPH_ENABLED", "false")
    assert records_kinds("Which requirements don't have supporting evidence in our records?") == []
    assert heuristic_route("Who owns the BVN obligation?")["intent"] != "compliance_records"
    assert not chat.wanted("How does this circular relate to our policy?")


@pytest.fixture
async def world(db, monkeypatch):
    f.user(db, "iroko", role="superadmin", workspace="ws-lib")
    ada = f.user(db, "ada", role="admin", workspace="ws-a")
    bola = f.user(db, "bola", role="admin", workspace="ws-b")
    f.document(db, "bvn", title="BVN Enrollment for OFIs Customers", pages=[f.BVN_LETTER], workspace="ws-lib",
               shared=True, regulator="CBN", reference="OFI/DIR/CIR/GEN/17/139", uploaded_by="iroko")
    f.document(db, "pol", title="AML/CFT Policy", pages=[f.AML_POLICY], workspace="ws-a", role="policy",
               uploaded_by="ada")
    f.document(db, "bpol", title="B private policy", pages=[f.AML_POLICY], workspace="ws-b", role="policy",
               uploaded_by="bola")
    await extract(db, "bvn")
    await extract(db, "pol", f.FakeModel(role="policy"))
    await extract(db, "bpol", f.FakeModel(role="policy"))
    review.set_profile(db, for_user(db, ada), ["state"])
    review.set_profile(db, for_user(db, bola), ["state"])
    await sync(db, "ws-a")
    await sync(db, "ws-b")
    monkeypatch.setattr("ingestion.db.Session", lambda: contextlib.nullcontext(db))
    return {"ada": ada, "bola": bola}


def bvn_sources(db):
    from services.compliance_graph.chat import chunk_source

    obligation = db.query(Obligation).filter(Obligation.document_id == "bvn").first()
    return [chunk_source(db, Principal("ada", "admin"), obligation.chunk_id)]


async def test_records_answers_cite_exact_words_and_never_state_a_verdict(db, world):
    with as_user(world["ada"]):
        gaps = chat.records_answer(["gaps"], "Which requirements don't have supporting evidence in our records?")
        due = chat.records_answer(["owners", "due"], "Who owns the BVN obligation, and what is due next?")
        trace = chat.records_answer(["trace"], "Trace the BVN withdrawal requirement")
    assert "Not established in Iroko's records" in gaps["answer"] and "not a compliance finding" in gaps["answer"]
    assert gaps["citations"] and all(c["chunk_id"].startswith("bvn_chunk_") for c in gaps["citations"])
    for result in (gaps, due, trace):
        assert not wording.has_verdict_wording(result["answer"])
        assert result["answer_status"] == "answered"
    assert "no owner recorded in Iroko" in due["answer"]
    assert "Requirement:" in trace["answer"]


def test_generic_words_never_narrow_a_records_question():
    rows = [{"summary": "Support rebuttal of the presumption with supportable information", "quote": "IFRS 9 text",
             "document": {"title": "IFRS 9 guidance"}},
            {"summary": "Enrol every customer for a BVN", "quote": "BVN text", "document": {"title": "BVN circular"}}]
    assert chat._topic_rows("Which requirements don't have supporting evidence in our records?", rows) == []
    assert chat._topic_rows("Who owns the BVN requirement?", rows) == [rows[1]]


async def test_trace_names_the_control_it_shows(db, world):
    from models.compliance_graph import Control

    ada = for_user(db, world["ada"])
    links = db.query(Link).filter(Link.workspace_id == "ws-a", Link.relation == "addresses").all()
    for link in links:
        review.review_link(db, ada, link.id, "confirm")
    db.commit()
    names = {db.get(Control, link.from_id).name for link in links}
    with as_user(world["ada"]):
        trace = chat.records_answer(["trace"], "Trace the monthly BVN enrollment returns requirement")
    assert "**Control:**" in trace["answer"] and "A control —" not in trace["answer"]
    assert any(name in trace["answer"] for name in names)


async def test_expansion_adds_confirmed_facts_only_and_counts_suggestions(db, world):
    actor = Principal("ada", "admin")
    sources = bvn_sources(db)
    before = chat._expand(db, actor, "How does this circular relate to our AML policy?", {"sources": sources})
    assert before["graph"]["records"] == 0 and before["graph"]["pending"] > 0
    for link in db.query(Link).filter(Link.workspace_id == "ws-a", Link.relation == "addresses"):
        review.review_link(db, for_user(db, world["ada"]), link.id, "confirm")
    after = chat._expand(db, actor, "How does this circular relate to our AML policy?", {"sources": sources})
    records = [s for s in after["sources"] if s["provenance"].get("source_kind") == "iroko_record"]
    assert records and all(s["title"] == "Iroko compliance record" for s in records)
    assert any(s["document_id"] == "pol" for s in after["sources"])  # the policy passage the link rests on
    assert after["knowledge_gap"] is False and after["retrieval_status"] == "ok"
    assert not any(s["document_id"] == "bpol" for s in after["sources"])
    other = chat._expand(db, Principal("bola", "admin"), "How does this circular relate to our policy?",
                         {"sources": sources})
    assert not any(s["document_id"] in ("pol", "record:ws-a") for s in other["sources"])


async def test_strategist_cites_records_after_the_quote_audit(db, world, monkeypatch):
    from agents.strategist import StrategistAgent

    for link in db.query(Link).filter(Link.workspace_id == "ws-a", Link.relation == "addresses"):
        review.review_link(db, for_user(db, world["ada"]), link.id, "confirm")
    sources = bvn_sources(db)

    async def retrieve(_question):
        return {"sources": [dict(s) for s in sources], "knowledge_gap": False, "retrieval_status": "ok"}

    async def complete(prompt, **kwargs):
        properties = kwargs["json_schema"]["properties"]
        payload = json.loads(prompt)
        if "intent" in properties:
            return json.dumps({"intent": "document_query", "reference_turn": None, "source_title_index": None,
                               "missing": "none"})
        if "supported_claims" in properties:
            return json.dumps({"answerable": True, "issues": [], "supported_claims": [True] * len(payload["claims"]),
                               "supported_calculations": [], "missing_information": []})
        record = next(e for e in payload["evidence"] if e["provenance"].get("source_kind") == "iroko_record")
        quote = record["content"].split(" that ", 1)[1][:120]
        return json.dumps({"answerable": True, "missing_information": [], "calculations": [], "direct_answer": None,
                           "claims": [{"text": "Your team confirmed a control in the AML/CFT Policy addresses the BVN requirement.",
                                       "chunk_id": record["chunk_id"], "quote": quote, "additional_evidence": []}]})

    monkeypatch.setattr("services.grounded_answers.retrieve", retrieve)
    monkeypatch.setattr("agents.strategist.llm_complete", complete)
    monkeypatch.setattr("services.regulatory_research.eligible", lambda _q: False)
    agent = StrategistAgent()
    agent.graph_step = lambda question, context: chat._expand(db, Principal("ada", "admin"), question, context)
    agent.graph_timeout = 30  # a loaded test machine must not turn this into the documents-only fallback
    with as_user(world["ada"]):
        result = json.loads(await agent.investigate("How does the BVN circular relate to our AML policy?"))
    assert result["answer_status"] == "answered", result
    record_citations = [c for c in result["citations"] if (c.get("provenance") or {}).get("source_kind") == "iroko_record"]
    assert record_citations and record_citations[0]["provenance"]["record_url"].startswith("/knowledge-graph?link=")
    assert any(step["tool"] == "graph" for step in result["agent_trace"])
