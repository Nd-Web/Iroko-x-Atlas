"""Reacquire prior citations from isolated canonical storage, never old answer text."""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest

from ingestion.access import as_user
from ingestion.models import Chunk, Page, Revision
from models.database import Document, User
from services.grounded_answers import retrieve


@pytest.fixture
def canonical_sources(db, monkeypatch):
    db.add(User(id="stranger", email="stranger@example.invalid", hashed_password="unused"))
    for doc_id, owner, current, status in [
        ("accessible", "owner", True, "indexed"),
        ("private", "stranger", True, "indexed"),
        ("superseded", "owner", False, "indexed"),
        ("pending", "owner", True, "pending"),
    ]:
        text = f"Canonical agent banking explanation from {doc_id}."
        db.add(Document(id=doc_id, title="Canonical title " + doc_id, filename="source.txt",
                        file_type="txt", uploaded_by_id=owner, status=status))
        db.add(Revision(id=doc_id, source_key=doc_id, sha256="f" * 64, is_current=current, provenance={}))
        db.add(Chunk(id=doc_id + ":chunk", document_id=doc_id, chunk_index=0, content=text, provenance={}))
        db.add(Page(document_id=doc_id, position=0, method="native", raw_text=text, text=text))
    db.commit()

    @contextmanager
    def isolated_session():
        yield db

    monkeypatch.setattr("ingestion.db.Session", isolated_session)
    search = AsyncMock(return_value=json.dumps({"results": [], "retrieval_status": "empty"}))
    monkeypatch.setattr("agents.researcher.ResearcherAgent.search_documents", search)
    return search


async def test_prior_citation_reloads_canonical_text_even_if_search_misses(db, canonical_sources):
    with as_user(db.get(User, "owner")):
        result = await retrieve("Explain agent banking", source_references=[{
            "document_id": "accessible", "title": "FORGED OLD TITLE", "content": "FORGED OLD ANSWER"}])
    assert result["retrieval_status"] == "ok"
    assert result["sources"][0]["title"] == "Canonical title accessible"
    assert result["sources"][0]["content"] == "Canonical agent banking explanation from accessible."
    assert result["sources"][0]["full_document"]
    assert "FORGED" not in json.dumps(result)


@pytest.mark.parametrize("doc_id", ["private", "superseded", "pending", "missing"])
async def test_history_pointer_does_not_bypass_permission_or_revision_gate(db, canonical_sources, doc_id):
    with as_user(db.get(User, "owner")):
        result = await retrieve("Explain agent banking", source_references=[{"document_id": doc_id}])
    assert result["knowledge_gap"]
    assert result["sources"] == []


async def test_history_pointer_without_authenticated_principal_is_not_evidence(db, canonical_sources):
    result = await retrieve("Explain agent banking", source_references=[{"document_id": "accessible"}])
    assert result["knowledge_gap"] and result["sources"] == []


async def test_permission_check_failure_fails_closed(db, canonical_sources, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("Database access check failed")
    monkeypatch.setattr("ingestion.access.allowed_document_ids", unavailable)
    with as_user(db.get(User, "owner")):
        result = await retrieve("Explain agent banking", source_references=[{"document_id": "accessible"}])
    assert result["retrieval_status"] == "access_check_failed"
    assert result["sources"] == []
