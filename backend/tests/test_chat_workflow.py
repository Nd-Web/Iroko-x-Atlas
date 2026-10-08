"""End-to-end chat contracts using real routing/auditing and isolated storage.

All evidence, model output, and regulator requests are mocked. The repository's
configured database and cloud services are deliberately unreachable from here.
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.strategist import StrategistAgent
from models.database import Base, Conversation, Message, User


FACTUAL_CASES = [
    ("document_query", "Summarise the uploaded incident report."),
    ("regulatory_compliance", "What regulatory compliance issue does the register identify?"),
    ("network_operations", "Which network incident remains unresolved?"),
    ("customer_complaint", "Which customer complaint remains unresolved?"),
    ("fraud_intelligence", "Which fraud issue remains unresolved?"),
]
QUOTE = "The register records an unresolved issue."
SUPPORTED = "The register describes an unresolved issue."
UNSUPPORTED = "The register confirms all issues were resolved."


def source():
    return {
        "chunk_id": "workflow-chunk",
        "document_id": "workflow-document",
        "title": "Incident register",
        "content": QUOTE,
        "provenance": {},
    }


def claim(text=SUPPORTED, quote=QUOTE):
    return {"text": text, "chunk_id": "workflow-chunk", "quote": quote, "additional_evidence": []}


@pytest.fixture(autouse=True)
def forbid_real_services(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise AssertionError("This test must never use the configured database or cloud services")

    monkeypatch.setattr("models.database.SessionLocal", unavailable)
    monkeypatch.setattr("ingestion.db.Session", unavailable)
    monkeypatch.setattr("agents.strategist.llm_complete", AsyncMock(side_effect=unavailable))
    monkeypatch.setattr("services.grounded_answers.retrieve", AsyncMock(side_effect=unavailable))
    monkeypatch.setattr("services.regulatory_research.research", AsyncMock(side_effect=unavailable))


@pytest.fixture
def evidence_pipeline(monkeypatch):
    """Keep production validation; replace only external calls with fixtures."""
    state = {"claims": [claim()], "supported": [True], "missing": [], "payloads": []}
    retrieve = AsyncMock(return_value={"sources": [source()], "knowledge_gap": False})
    monkeypatch.setattr("services.grounded_answers.retrieve", retrieve)
    # Public research is tested separately; these fixtures represent available
    # permission-checked internal evidence for each factual intent.
    monkeypatch.setattr("services.regulatory_research.eligible", lambda _question: False)

    async def complete(prompt, **kwargs):
        payload = json.loads(prompt)
        state["payloads"].append(payload)
        properties = kwargs["json_schema"]["properties"]
        if "intent" in properties:
            return json.dumps({"intent": "follow_up", "reference_turn": 0,
                               "source_title_index": 0, "missing": "none"})
        if "supported_claims" in properties:
            return json.dumps({"answerable": not state["missing"], "issues": [],
                               "supported_claims": state["supported"],
                               "supported_calculations": [], "missing_information": state["missing"]})
        return json.dumps({"answerable": not state["missing"], "claims": state["claims"],
                           "calculations": [], "missing_information": state["missing"]})

    model = AsyncMock(side_effect=complete)
    monkeypatch.setattr("agents.strategist.llm_complete", model)
    state.update(model=model, retrieve=retrieve)
    return state


@pytest.mark.parametrize("intent,question", FACTUAL_CASES)
async def test_every_factual_intent_retrieves_then_drafts_and_audits(evidence_pipeline, intent, question):
    state = evidence_pipeline
    result = json.loads(await StrategistAgent().investigate(question))
    assert result["intent"] == intent
    assert result["answer_status"] == "answered"
    assert SUPPORTED in result["answer"]
    assert result["citations"][0]["chunk_id"] == "workflow-chunk"
    state["retrieve"].assert_awaited_once_with(question)
    assert state["model"].await_count == 2
    assert "evidence" in state["payloads"][0]
    assert state["payloads"][1]["claims"][0]["text"] == SUPPORTED
    assert result["verdict"] == "MONITOR"
    assert any(step["tool"] == "claim_validation" for step in result["agent_trace"])


@pytest.mark.parametrize("intent,question", FACTUAL_CASES)
async def test_every_factual_intent_rejects_semantically_false_claim(evidence_pipeline, intent, question):
    state = evidence_pipeline
    state.update(claims=[claim(UNSUPPORTED)], supported=[False])
    result = json.loads(await StrategistAgent().investigate(question))
    assert result["intent"] == intent
    assert result["knowledge_gap"] is True
    assert result["gap_reason"] == "validation_failed"
    assert UNSUPPORTED not in result["answer"]
    assert result["citations"] == []
    assert state["model"].await_count == 4  # One bounded, re-audited repair.


@pytest.mark.parametrize("intent,question", FACTUAL_CASES)
async def test_every_factual_intent_rejects_fabricated_quotation(evidence_pipeline, intent, question):
    state = evidence_pipeline
    state["claims"] = [claim(UNSUPPORTED, "The register states that every issue was resolved.")]
    result = json.loads(await StrategistAgent().investigate(question))
    assert result["intent"] == intent
    assert result["knowledge_gap"] is True
    assert result["citations"] == []
    assert UNSUPPORTED not in result["answer"]
    assert state["model"].await_count == 2  # Invalid quotes never reach semantic audit.
    assert all("claims" not in payload for payload in state["payloads"])


@pytest.mark.parametrize("question", [
    "Thanks, which fraud issue remains unresolved?",
    "Hello, what regulatory compliance issue does the register identify?",
    "Ok thats nice but summarise the uploaded report.",
])
async def test_greeting_with_factual_request_still_runs_evidence_checks(evidence_pipeline, question):
    result = json.loads(await StrategistAgent().investigate(question))
    assert result["intent"] not in {"greeting", "out_of_domain"}
    assert result["citations"]
    assert evidence_pipeline["model"].await_count == 2


@pytest.mark.parametrize("question", ["tell me more", "does that apply to us?", "summarise this document"])
async def test_missing_referent_asks_clarification_without_search_or_model(monkeypatch, question):
    from agents import strategist
    from services import grounded_answers

    result = json.loads(await StrategistAgent().investigate(question))
    assert result["answer_status"] == "needs_clarification"
    assert result["citations"] == []
    assert not result["knowledge_gap"]
    strategist.llm_complete.assert_not_awaited()
    grounded_answers.retrieve.assert_not_awaited()


async def test_partial_answer_keeps_verified_fact_and_exposes_missing_part(evidence_pipeline):
    evidence_pipeline["missing"] = ["penalty"]
    result = json.loads(await StrategistAgent().investigate("What compliance issue is recorded and what penalty applies?"))
    assert result["answer_status"] == "partial"
    assert result["partial_answer"]
    assert "penalty" in result["missing_information"]
    assert SUPPORTED in result["answer"]
    assert result["citations"][0]["chunk_id"] == "workflow-chunk"
    assert result["suggested_actions"] or result["suggested_followups"]


async def test_stream_never_exposes_a_draft_while_evidence_audit_is_pending(monkeypatch, evidence_pipeline):
    audit_started = asyncio.Event()
    release_audit = asyncio.Event()
    original = evidence_pipeline["model"]

    async def delayed_complete(prompt, **kwargs):
        if "supported_claims" in kwargs["json_schema"]["properties"]:
            audit_started.set()
            await release_audit.wait()
        return await original(prompt, **kwargs)

    monkeypatch.setattr("agents.strategist.llm_complete", delayed_complete)
    events = []

    async def consume():
        async for event in StrategistAgent().investigate_stream("Summarise the uploaded incident report."):
            events.append(event)

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(audit_started.wait(), timeout=3)
        assert events and events[0]["type"] == "start"
        assert not any(item["type"] in {"token", "complete"} for item in events)
        release_audit.set()
        await asyncio.wait_for(task, timeout=3)
        assert events[-1]["type"] == "complete"
        assert events[-1]["citations"][0]["chunk_id"] == "workflow-chunk"
        assert "".join(item["content"] for item in events if item["type"] == "token") == events[-1]["answer"]
    finally:
        release_audit.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_followup_uses_saved_context_without_treating_prior_answer_as_evidence(evidence_pipeline):
    agent = StrategistAgent()
    agent.set_history([{
        "question": "What does the incident register show?",
        "answer_summary": "UNVERIFIED HISTORICAL CLAIM: all issues were resolved.",
        "citations": [{"document_title": "Incident register", "document_id": "workflow-document"}],
    }, {"question": "ok thats nice", "answer_summary": "You are welcome."}])
    result = json.loads(await agent.investigate("does that apply to our MFB?"))
    assert result["intent"] == "follow_up"
    query = evidence_pipeline["retrieve"].call_args.args[0]
    assert "What does the incident register show?" in query
    assert "does that apply to our MFB?" in query
    assert "ok thats nice" not in query
    drafting = next(payload for payload in evidence_pipeline["payloads"] if "evidence" in payload)
    assert "UNVERIFIED HISTORICAL CLAIM" in json.dumps(drafting["conversation_context"])
    assert "UNVERIFIED HISTORICAL CLAIM" not in json.dumps(drafting["evidence"])
    assert "UNVERIFIED HISTORICAL CLAIM" not in result["answer"]


async def test_fresh_official_findings_keep_partial_status_and_skip_unused_local_search(monkeypatch, evidence_pipeline):
    official = {**source(), "provenance": {"official_live": True, "source_url": "https://www.cbn.gov.ng/fixture"}}
    report = {"sources": [official], "checks": [{"regulator": "CBN", "url": "https://www.cbn.gov.ng/fixture", "status": "checked"}],
              "checked_at": "2026-10-06T12:00:00+00:00"}
    research = AsyncMock(return_value=report)
    monkeypatch.setattr("services.regulatory_research.eligible", lambda _question: True)
    monkeypatch.setattr("services.regulatory_research.research", research)
    result = json.loads(await StrategistAgent().investigate("What are the latest CBN compliance announcements?"))
    assert SUPPORTED in result["answer"]
    assert result["partial_answer"]
    assert result["answer_status"] == "partial"
    assert "latest_coverage" in result["missing_information"]
    assert result["source_checks"] == report["checks"]
    assert result["research_checked_at"] == report["checked_at"]
    research.assert_awaited_once()
    evidence_pipeline["retrieve"].assert_not_awaited()


@pytest.fixture
def stored_chat(monkeypatch):
    from ingestion.models import PipelineBase
    from models.database import get_db
    from routes import ask

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, execution_options={"schema_translate_map": {"ingestion": None}})
    Base.metadata.create_all(engine)
    PipelineBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("models.database.SessionLocal", factory)
    monkeypatch.setattr(ask, "_check_rate_limit", lambda _user: True)
    with factory() as db:
        owner = User(id="workflow-owner", email="workflow-owner@example.invalid", hashed_password="unused", role="analyst")
        other = User(id="workflow-other", email="workflow-other@example.invalid", hashed_password="unused", role="analyst")
        db.add_all([owner, other])
        db.add(Conversation(id="private-conversation", user_id=other.id, title="Private topic"))
        db.add(Message(conversation_id="private-conversation", role="user", content="PRIVATE OTHER USER TOPIC"))
        db.commit()
        app = FastAPI()
        app.include_router(ask.router)
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db, owner
    engine.dispose()


def headers(owner):
    from services.auth_utils import create_access_token
    return {"Authorization": "Bearer " + create_access_token(owner.id, owner.role)}


def stream_events(response):
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"]


@pytest.mark.parametrize("path", ["/api/atlas/ask", "/api/atlas/ask/stream-http"])
def test_foreign_conversation_id_cannot_load_or_extend_history(stored_chat, evidence_pipeline, path):
    client, db, owner = stored_chat
    response = client.post(path, json={"query": "tell me more", "conversation_id": "private-conversation"}, headers=headers(owner))
    assert response.status_code == 404
    assert db.query(Conversation).count() == 1
    assert db.query(Message).count() == 1
    evidence_pipeline["retrieve"].assert_not_awaited()
    evidence_pipeline["model"].assert_not_awaited()


def test_stream_completion_carries_partial_status_and_saved_context(stored_chat, evidence_pipeline):
    client, db, owner = stored_chat
    evidence_pipeline["missing"] = ["penalty"]
    first = stream_events(client.post("/api/atlas/ask/stream-http", json={
        "query": "What regulatory compliance issue is recorded and what penalty applies?",
    }, headers=headers(owner)))[-1]
    assert first["type"] == "complete"
    assert first["answer_status"] == "partial"
    assert first["gap_reason"] == "incomplete_evidence"
    saved = db.get(Message, first["message_id"])
    assert saved.content == first["answer"]
    assert saved.citations == first["citations"]
    assert any(step.get("answer_status") == "partial" for step in saved.agent_trace)

    second = stream_events(client.post("/api/atlas/ask/stream-http", json={
        "query": "tell me more", "conversation_id": first["conversation_id"],
    }, headers=headers(owner)))[-1]
    assert second["type"] == "complete"
    assert second["conversation_id"] == first["conversation_id"]
    assert evidence_pipeline["retrieve"].call_args.args[0].startswith("What regulatory compliance issue")
    assert "Follow-up: tell me more" in evidence_pipeline["retrieve"].call_args.args[0]
    saved_followup = db.get(Message, second["message_id"])
    assert any("resolved_question" in step for step in saved_followup.agent_trace)
    assert "PRIVATE OTHER USER TOPIC" not in json.dumps(evidence_pipeline["payloads"])


def test_normal_and_stream_endpoints_keep_same_outcome_metadata(stored_chat, evidence_pipeline):
    client, _db, owner = stored_chat
    evidence_pipeline["missing"] = ["penalty"]
    body = {"query": "What compliance issue is recorded and what penalty applies?"}
    normal = client.post("/api/atlas/ask", json=body, headers=headers(owner))
    assert normal.status_code == 200, normal.text
    streamed = stream_events(client.post("/api/atlas/ask/stream-http", json=body, headers=headers(owner)))[-1]
    for key in ("answer", "answer_status", "gap_reason", "partial_answer", "missing_information", "suggested_actions", "suggested_followups"):
        assert normal.json()[key] == streamed[key], key
    # The non-stream Pydantic response adds an optional relevance_score default;
    # compare factual identity and coordinates rather than that display default.
    assert len(normal.json()["citations"]) == len(streamed["citations"])
    for normal_citation, stream_citation in zip(normal.json()["citations"], streamed["citations"]):
        for key in ("document_id", "document_title", "chunk_id", "excerpt", "provenance", "source_url"):
            assert normal_citation[key] == stream_citation[key]


def test_normal_endpoint_cannot_save_internal_failure_as_answered(stored_chat, monkeypatch):
    from models.database import AgentRun

    client, db, owner = stored_chat
    monkeypatch.setattr(StrategistAgent, "investigate", AsyncMock(return_value=json.dumps({
        "error": "request_failed", "answer": "The chat service could not complete this request.",
    })))
    response = client.post("/api/atlas/ask", json={"query": "Explain the report"}, headers=headers(owner))
    assert response.status_code == 503
    assert db.query(Message).filter_by(role="assistant").count() == 0
    assert db.query(AgentRun).filter_by(success=True).count() == 0


def test_saved_history_restores_resolved_topic_and_bounds_prior_answer(stored_chat):
    from routes.ask import _load_history

    _client, db, owner = stored_chat
    now = datetime(2026, 10, 6, 12)
    db.add(Conversation(id="saved-context", user_id=owner.id, title="Saved context"))
    db.add_all([
        Message(conversation_id="saved-context", role="user", content="tell me more", created_at=now),
        Message(conversation_id="saved-context", role="assistant", content="Context " * 500,
                created_at=now + timedelta(seconds=1),
                agent_trace=[{"tool": "conversation_context", "resolved_question": "Original report question\nFollow-up: tell me more"}],
                citations=[{"document_title": "Saved title", "document_id": "saved-document", "excerpt": "OLD QUOTE IS NOT EVIDENCE"}]),
    ])
    db.commit()
    history = _load_history(db, "saved-context")
    assert len(history) == 1
    assert history[0]["resolved_question"].startswith("Original report question")
    assert len(history[0]["answer_summary"]) <= 1200
    assert history[0]["citations"] == [{"document_id": "saved-document", "document_title": "Saved title"}]
    assert "PRIVATE OTHER USER TOPIC" not in json.dumps(history)
    assert "OLD QUOTE IS NOT EVIDENCE" not in json.dumps(history)
