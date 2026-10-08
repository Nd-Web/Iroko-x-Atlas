"""Per-answer feedback: the user's verdict on each answer, scoped to their own conversations."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ingestion.models import PipelineBase
from models.database import AnswerFeedback, Base, Conversation, Message, User


@pytest.fixture
def chat(monkeypatch):
    from models.database import get_db
    from routes import ask
    from services.auth_utils import create_access_token

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
                           execution_options={"schema_translate_map": {"ingestion": None}})
    Base.metadata.create_all(engine)
    PipelineBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add_all([User(id=uid, email=f"{uid}@example.invalid", hashed_password="unused", role="analyst")
                for uid in ("owner", "other")])
    db.add_all([Conversation(id="mine", user_id="owner"), Conversation(id="theirs", user_id="other")])
    db.add_all([
        Message(id="q1", conversation_id="mine", role="user", content="What is the CTR deadline?"),
        Message(id="a1", conversation_id="mine", role="assistant", content="Within 7 days. [1]"),
        Message(id="a2", conversation_id="theirs", role="assistant", content="Private answer."),
    ])
    db.commit()
    monkeypatch.setattr("models.database.SessionLocal", lambda: db)
    app = FastAPI()
    app.include_router(ask.router)
    app.dependency_overrides[get_db] = lambda: db
    headers = {"Authorization": "Bearer " + create_access_token("owner", "analyst")}
    with TestClient(app) as client:
        yield client, db, headers
    db.close()
    engine.dispose()


def test_thumbs_down_with_reason_is_stored_and_shown_with_history(chat):
    client, db, headers = chat
    response = client.post("/api/atlas/messages/a1/feedback",
                           json={"helpful": False, "reason": "missed_part", "comment": "No CTR recipient."}, headers=headers)
    assert response.status_code == 200, response.text
    saved = db.query(AnswerFeedback).filter_by(message_id="a1", user_id="owner").one()
    assert (saved.helpful, saved.reason, saved.comment) == (False, "missed_part", "No CTR recipient.")
    history = client.get("/api/atlas/conversations/mine/messages", headers=headers).json()["messages"]
    assert history[1]["feedback"] == {"helpful": False, "reason": "missed_part"}
    assert history[0]["feedback"] is None


def test_voting_again_replaces_the_verdict_and_clears_the_reason(chat):
    client, db, headers = chat
    client.post("/api/atlas/messages/a1/feedback", json={"helpful": False, "reason": "wrong_fact"}, headers=headers)
    response = client.post("/api/atlas/messages/a1/feedback", json={"helpful": True, "reason": "wrong_fact"}, headers=headers)
    assert response.json() == {"status": "ok", "message_id": "a1", "helpful": True, "reason": None}
    assert db.query(AnswerFeedback).count() == 1


@pytest.mark.parametrize("message_id", ["a2", "q1", "missing"])
def test_only_answers_in_your_own_conversations_can_be_rated(chat, message_id):
    client, db, headers = chat
    response = client.post(f"/api/atlas/messages/{message_id}/feedback", json={"helpful": True}, headers=headers)
    assert response.status_code == 404
    assert db.query(AnswerFeedback).count() == 0


def test_unknown_reason_is_rejected(chat):
    client, _db, headers = chat
    response = client.post("/api/atlas/messages/a1/feedback", json={"helpful": False, "reason": "bad"}, headers=headers)
    assert response.status_code == 422


def test_feedback_requires_sign_in(chat):
    client, _db, _headers = chat
    assert client.post("/api/atlas/messages/a1/feedback", json={"helpful": True}).status_code == 401


def test_export_turns_thumbs_down_into_review_ready_eval_cases(chat):
    import sys
    from datetime import datetime
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from export_answer_feedback import collect, eval_candidates

    client, db, headers = chat
    answer = db.get(Message, "a1")
    answer.created_at = datetime(2026, 10, 6, 12, 0, 1)
    db.get(Message, "q1").created_at = datetime(2026, 10, 6, 12)
    answer.agent_trace = [{"tool": "conversation_context", "resolved_question": "What is the CTR deadline in the 2017 circular?"},
                          {"tool": "answer_outcome", "answer_status": "partial"}]
    answer.citations = [{"document_id": "aml-2017", "document_title": "AML/CFT returns"}]
    db.commit()
    client.post("/api/atlas/messages/a1/feedback",
                json={"helpful": False, "reason": "missed_part", "comment": "Should say: to the NFIU within 7 days."}, headers=headers)
    rows = collect(db)
    assert len(rows) == 1
    assert rows[0]["question"] == "What is the CTR deadline?"
    assert rows[0]["cited_documents"] == ["AML/CFT returns"]
    assert rows[0]["answer_status"] == "partial"
    [case] = eval_candidates(rows)
    assert case["question"] == "What is the CTR deadline in the 2017 circular?"  # The resolved question.
    assert case["expected"] == "Should say: to the NFIU within 7 days."
    assert case["review_status"] == "needs_review"
    client.post("/api/atlas/messages/a1/feedback", json={"helpful": True}, headers=headers)
    assert eval_candidates(collect(db)) == []
