"""Authenticated streaming regressions. No production writes or model calls."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from ingestion.access import principal
from models.database import Conversation, Message, User, get_db
from services.auth_utils import create_access_token


@pytest.fixture
def chat(db, monkeypatch):
    from routes import ask

    monkeypatch.setattr(ask, "_check_rate_limit", lambda user_id: True)
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr("models.database.SessionLocal", factory)

    class FakeStrategist:
        def set_history(self, history):
            self.history = history

        async def investigate(self, question):
            assert principal.get().id == "owner"
            return json.dumps({"answer": "Verified official finding", "agent_trace": [],
                "citations": [{"document_id": "public:doc", "document_title": "Official source",
                               "excerpt": "Verified source quote", "source_url": "https://www.cbn.gov.ng/test"}],
                "partial_answer": True, "missing_information": ["penalty"],
                "source_checks": [{"regulator": "CBN", "url": "https://www.cbn.gov.ng/test", "status": "checked"}],
                "research_checked_at": "2026-10-03T00:00:00+00:00"})

        async def investigate_stream(self, question):
            assert principal.get().id == "owner"
            yield {"type": "start", "message": "Checking evidence"}
            if question == "fail":
                yield {"type": "error", "message": "Model unavailable"}
                return
            if question == "truncate":
                return
            answer = "Verified reply" if not self.history else "Verified follow-up"
            yield {"type": "token", "content": answer}
            yield {"type": "complete", "answer": answer, "agent_trace": [], "citations": []}

    monkeypatch.setattr(ask, "StrategistAgent", FakeStrategist)
    app = FastAPI()
    app.include_router(ask.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def send(chat, query, conversation=None):
    response = chat.post("/api/atlas/ask/stream-http", json={
        "query": query, "conversation_id": conversation,
    }, headers={"Authorization": "Bearer " + create_access_token("owner", "admin")})
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"]


def test_reply_saved_before_complete_and_followup_reuses_conversation(chat, db):
    events = send(chat, "Question")
    complete = events[-1]
    assert complete["type"] == "complete"
    assert events[0]["conversation_id"] == complete["conversation_id"]
    assert db.get(Message, complete["message_id"]).content == "Verified reply"
    second = send(chat, "Follow-up", complete["conversation_id"])[-1]
    assert second["conversation_id"] == complete["conversation_id"]
    assert second["answer"] == "Verified follow-up"
    assert db.query(Conversation).count() == 1
    assert db.query(Message).count() == 4


@pytest.mark.parametrize("query", ["fail", "truncate"])
def test_failed_stream_never_saves_empty_reply_or_claims_success(chat, db, query):
    events = send(chat, query)
    assert events[-1]["type"] == "error"
    assert not any(e["type"] == "complete" for e in events)
    assert db.query(Message).filter_by(role="assistant").count() == 0


def test_cookie_proxy_cannot_bypass_backend_auth(chat):
    response = chat.post("/api/atlas/ask/stream-http", json={"query": "Question"})
    assert response.status_code == 401


def test_normal_endpoint_preserves_research_metadata_and_persisted_public_citations(chat, db):
    response = chat.post("/api/atlas/ask", json={"query": "latest CBN risk and penalty"},
                         headers={"Authorization": "Bearer " + create_access_token("owner", "admin")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["partial_answer"] and result["missing_information"] == ["penalty"]
    assert result["research_checked_at"] and result["source_checks"][0]["status"] == "checked"
    assert result["citations"][0]["source_url"] == "https://www.cbn.gov.ng/test"
    assert db.get(Message, result["message_id"]).citations[0]["source_url"] == "https://www.cbn.gov.ng/test"


async def test_heartbeat_keeps_slow_validated_answer_stream_alive():
    from routes.ask import _with_heartbeats

    async def slow():
        await asyncio.sleep(0.03)
        yield "verified answer"

    events = [event async for event in _with_heartbeats(slow(), interval=0.005)]
    assert events[0] == ": keep-alive\n\n"
    assert events[-1] == "verified answer"


async def test_disconnect_cancels_pending_work():
    from routes.ask import _with_heartbeats
    cancelled = False

    async def slow():
        nonlocal cancelled
        try:
            await asyncio.sleep(60)
            yield "never sent"
        finally:
            cancelled = True

    stream = _with_heartbeats(slow(), interval=0.001)
    assert await anext(stream) == ": keep-alive\n\n"
    await stream.aclose()
    assert cancelled


async def test_model_error_is_a_stream_error_not_an_answer(monkeypatch):
    from agents.strategist import StrategistAgent
    agent = StrategistAgent()
    monkeypatch.setattr(agent, "investigate", AsyncMock(return_value=json.dumps({
        "answer": "I encountered an error", "error": "private upstream diagnostics",
    })))
    events = [event async for event in agent.investigate_stream("Question")]
    assert events[-1]["type"] == "error"
    assert not any(e["type"] in {"token", "complete"} for e in events)
    assert "private" not in json.dumps(events)


async def test_progress_is_emitted_before_validated_tokens(monkeypatch):
    from agents.strategist import StrategistAgent
    agent = StrategistAgent()
    validated = False

    async def investigate(question, depth):
        nonlocal validated
        agent._log_trace("Researcher", "search", "Retrieving evidence")
        await asyncio.sleep(0.3)
        validated = True
        return json.dumps({"answer": "Verified answer", "agent_trace": agent.trace})

    monkeypatch.setattr(agent, "investigate", investigate)
    events = []
    async for event in agent.investigate_stream("Question"):
        if event["type"] == "agent_action":
            assert not validated
        if event["type"] == "token":
            assert validated
        events.append(event)
    assert [event["type"] for event in events] == ["start", "agent_action", "token", "complete"]
