"""Listing the document library in chat; isolated SQLite, no search or model calls."""

import json
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ingestion.access import Principal, as_user
from ingestion.models import DocumentAccess, Page, PipelineBase, Revision
from models.database import Base, Document, User
from services.chat_router import heuristic_route, route_question
from services.document_catalog import catalog_answer, list_documents

OWNER = Principal("owner", "analyst")


@pytest.fixture
def library(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
                           execution_options={"schema_translate_map": {"ingestion": None}})
    Base.metadata.create_all(engine)
    PipelineBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add_all([User(id=uid, email=f"{uid}@example.invalid", hashed_password="unused", role="analyst")
                for uid in ("owner", "other")])

    def add(doc_id, title, text, *, workspace="user:owner", shared=False, status="indexed",
            current=True, regulator=None, published=None, reference=None, owner="owner"):
        db.add(Document(id=doc_id, title=title, filename=f"{doc_id}.pdf", file_type="pdf", status=status,
                        uploaded_by_id=owner, created_at=datetime(2026, 1, 1)))
        provenance = {k: v for k, v in {"regulator": regulator, "published_date": published,
                                          "reference_number": reference}.items() if v}
        db.add(Revision(id=doc_id, source_key=doc_id, sha256=doc_id.ljust(64, "0"), is_current=current,
                        provenance=provenance))
        db.add(Page(document_id=doc_id, position=0, page_number=1, method="text", raw_text=text, text=text))
        db.add(DocumentAccess(document_id=doc_id, workspace_id=workspace, shared_regulatory=shared))

    add("bvn", "BVN Enrollment for OFIs Customers", "All accounts must carry a Bank Verification Number.",
        workspace="platform", shared=True, regulator="CBN", published="2017-04-21", reference="OFI/DIR/1")
    add("aml", "Rendition of Returns on AML/CFT", "Suspicious transaction reports go to the NFIU.",
        workspace="platform", shared=True, regulator="CBN", published="2017-05-02", reference="OFI/DIR/2")
    add("board", "Board paper", "The board approved the 2027 budget.")
    add("foreign", "Other bank BVN audit", "Bank Verification Number exceptions.", workspace="user:other", owner="other")
    add("queued", "Queued BVN upload", "Bank Verification Number policy.", status="processing")
    add("old", "Superseded BVN policy", "Bank Verification Number policy.", current=False)
    db.commit()

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr("ingestion.db.Session", session)
    yield db
    db.close()
    engine.dispose()


def test_lists_only_permitted_current_indexed_documents_newest_first(library):
    with as_user(OWNER):
        titles = [entry["title"] for entry in list_documents()]
    assert titles == ["Rendition of Returns on AML/CFT", "BVN Enrollment for OFIs Customers", "Board paper"]


@pytest.mark.parametrize("topic,expected", [
    ("BVN", ["BVN Enrollment for OFIs Customers"]),
    ("suspicious transaction reports", ["Rendition of Returns on AML/CFT"]),  # extracted text
    ("the budget", ["Board paper"]),
    ("OFI/DIR/2", ["Rendition of Returns on AML/CFT"]),  # reference number
    ("cryptocurrency", []),
])
def test_topic_matches_title_reference_or_extracted_text(library, topic, expected):
    with as_user(OWNER):
        assert [entry["title"] for entry in list_documents(topic)] == expected


def test_answer_groups_by_regulator_with_dates_and_suggests_questions(library):
    with as_user(OWNER):
        result = catalog_answer()
    answer = result["answer"]
    assert answer.startswith("You can access 3 processed documents:")
    assert "**CBN**" in answer and "**Your uploads**" in answer
    assert "- Rendition of Returns on AML/CFT (2 May 2017; OFI/DIR/2)" in answer
    assert "- Board paper" in answer
    assert "Other bank" not in answer and "Queued" not in answer and "Superseded" not in answer
    assert result["suggested_followups"][0] == "What are the key points in “Rendition of Returns on AML/CFT”?"
    assert result["citations"] == []


def test_documents_sharing_a_title_are_listed_but_suggested_once(monkeypatch):
    from datetime import date

    entries = [{"document_id": f"si-{n}", "title": "Revocation of Operating Licenses", "regulator": "CBN",
                "reference": f"S.I. No. {n} of 2023", "published": date(2023, 5, n)} for n in (23, 22)]
    entries.append({"document_id": "bvn", "title": "BVN Enrollment", "regulator": "CBN", "reference": "",
                    "published": date(2018, 1, 2)})
    monkeypatch.setattr("services.document_catalog.list_documents", lambda topic=None: entries)
    result = catalog_answer()
    assert result["answer"].count("Revocation of Operating Licenses") == 2
    assert result["suggested_followups"] == ["What are the key points in “Revocation of Operating Licenses”?",
                                             "What are the key points in “BVN Enrollment”?"]


def test_unmatched_topic_says_so_without_claiming_the_corpus_lacks_it(library):
    with as_user(OWNER):
        result = catalog_answer("cryptocurrency")
    assert "None of the documents you can access mention “cryptocurrency”" in result["answer"]
    assert "ask your question directly" in result["answer"]


def test_without_a_signed_in_principal_nothing_is_listed(library):
    result = catalog_answer()
    assert result["answer"].startswith("You don't have any processed documents yet.")
    assert result["catalog"] == []


@pytest.mark.parametrize("question,topic", [
    ("What documents do you have?", None),
    ("Which circulars do you have about BVN?", "BVN"),
    ("What documents mention suspicious transaction reports?", "suspicious transaction reports"),
    ("List all documents", None),
    ("Show me the circulars on anti-money laundering", "anti-money laundering"),
    ("Hi, what files have I uploaded?", None),
    ("What's in my library?", None),
    ("How many documents do you have?", None),
    ("Which documents are available?", None),
    ("Do you have any circulars on BVN?", "BVN"),
    ("Have I uploaded any documents?", None),
])
async def test_library_questions_route_to_catalog_without_a_model(question, topic):
    complete = AsyncMock()
    result = await route_question(question, complete=complete)
    assert result["intent"] == "catalog"
    assert result["catalog_topic"] == topic
    complete.assert_not_called()


@pytest.mark.parametrize("question", [
    "What does the BVN document say about post no debit?",
    "List the requirements in the AML circular",
    "Show me the report on Q2 AML returns",
    "Which document sets the CTR deadline?",
    "Do you have any documents that state the CTR deadline?",
])
def test_questions_about_document_content_are_not_catalog_requests(question):
    assert heuristic_route(question)["intent"] != "catalog"


def test_catalog_turn_is_not_a_follow_up_topic():
    history = [{"question": "What documents do you have?", "answer_summary": "You can access 3 documents.", "intent": "catalog"}]
    assert heuristic_route("Tell me more", history)["intent"] == "clarification"


async def test_chat_lists_library_without_search_or_model(library, monkeypatch):
    from agents.strategist import StrategistAgent

    monkeypatch.setattr("agents.strategist.llm_complete", AsyncMock(side_effect=AssertionError("no model call")))
    monkeypatch.setattr("services.grounded_answers.retrieve", AsyncMock(side_effect=AssertionError("no search")))
    with as_user(OWNER):
        result = json.loads(await StrategistAgent().investigate("Which circulars do you have about BVN?"))
    assert result["intent"] == "catalog"
    assert result["answer"].startswith("1 document you can access mentions “BVN”:")
    assert "BVN Enrollment for OFIs Customers" in result["answer"]
    assert "Other bank" not in result["answer"]
    assert result["suggested_followups"] == ["What are the key points in “BVN Enrollment for OFIs Customers”?"]
    assert any(step["tool"] == "catalog" for step in result["agent_trace"])


def test_stream_endpoint_delivers_and_saves_the_library_answer(library, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from models.database import Message, get_db
    from routes import ask
    from services.auth_utils import create_access_token

    monkeypatch.setattr("agents.strategist.llm_complete", AsyncMock(side_effect=AssertionError("no model call")))
    monkeypatch.setattr("models.database.SessionLocal", lambda: library)
    monkeypatch.setattr(ask, "_check_rate_limit", lambda _user: True)
    app = FastAPI()
    app.include_router(ask.router)
    app.dependency_overrides[get_db] = lambda: library
    with TestClient(app) as client:
        response = client.post("/api/atlas/ask/stream-http", json={"query": "Which circulars do you have about BVN?"},
                               headers={"Authorization": "Bearer " + create_access_token("owner", "analyst")})
    assert response.status_code == 200, response.text
    events = [json.loads(line[6:]) for line in response.text.splitlines()
              if line.startswith("data: ") and line != "data: [DONE]"]
    complete = events[-1]
    assert complete["type"] == "complete"
    assert "BVN Enrollment for OFIs Customers" in complete["answer"]
    assert "Other bank" not in complete["answer"]
    assert "".join(e["content"] for e in events if e["type"] == "token") == complete["answer"]
    saved = library.get(Message, complete["message_id"])
    assert saved.content == complete["answer"]
    assert any(step.get("suggested_followups") for step in saved.agent_trace)


async def test_chat_reports_access_failure_when_the_library_cannot_be_read(monkeypatch):
    from agents.strategist import StrategistAgent

    def broken():
        raise RuntimeError("database down")

    monkeypatch.setattr("ingestion.db.Session", broken)
    with as_user(OWNER):
        result = json.loads(await StrategistAgent().investigate("What documents do you have?"))
    assert result["gap_reason"] == "access_check_failed"
    assert "error" not in result
