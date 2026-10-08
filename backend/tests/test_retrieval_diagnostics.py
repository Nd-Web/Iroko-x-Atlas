"""Retrieval failures stay distinguishable without weakening document access checks."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agents import researcher
from ingestion import access
from services import azure_search


@pytest.fixture
def search_setup(monkeypatch):
    # Every data dependency is mocked: never connect to configured Postgres/Azure.
    token = access.principal.set(access.Principal("test-owner", "admin"))
    acl = Mock(return_value="search.in(doc_id, 'own-document', '|')")
    client = SimpleNamespace(search=Mock(return_value=[]))
    embedding = AsyncMock(return_value=None)
    post_filter = Mock(side_effect=lambda rows: list(rows))
    monkeypatch.setattr(access, "search_filter", acl)
    monkeypatch.setattr(azure_search, "get_search_client", lambda: client)
    monkeypatch.setattr("services.embeddings.get_embedding", embedding)
    monkeypatch.setattr(azure_search, "eligible_results", post_filter)
    yield SimpleNamespace(acl=acl, client=client, embedding=embedding, post_filter=post_filter)
    access.principal.reset(token)


async def test_completed_empty_search_is_not_an_outage(search_setup):
    result = await azure_search.hybrid_search_detailed("record retention")
    assert result == {"results": [], "retrieval_status": "empty"}
    assert search_setup.client.search.call_count == 1


async def test_missing_search_configuration_is_unavailable(search_setup, monkeypatch):
    monkeypatch.setattr(azure_search, "get_search_client", lambda: None)
    assert await azure_search.hybrid_search_detailed("policy") == {
        "results": [], "retrieval_status": "unavailable",
    }
    search_setup.embedding.assert_not_awaited()


async def test_both_search_attempts_fail_without_returning_exception(search_setup):
    search_setup.client.search.side_effect = RuntimeError("private endpoint credential")
    result = await azure_search.hybrid_search_detailed("policy")
    assert result == {"results": [], "retrieval_status": "unavailable"}
    assert search_setup.client.search.call_count == 2
    assert "credential" not in json.dumps(result)


async def test_acl_failure_stops_before_search_or_embedding(search_setup):
    search_setup.acl.side_effect = RuntimeError("database password private")
    result = await azure_search.hybrid_search_detailed("policy")
    assert result == {"results": [], "retrieval_status": "access_check_failed"}
    search_setup.embedding.assert_not_awaited()
    search_setup.client.search.assert_not_called()


async def test_missing_principal_is_access_failure(search_setup):
    token = access.principal.set(None)
    try:
        result = await azure_search.hybrid_search_detailed("policy")
    finally:
        access.principal.reset(token)
    assert result["retrieval_status"] == "access_check_failed"
    search_setup.acl.assert_not_called()
    search_setup.client.search.assert_not_called()


async def test_valid_empty_acl_does_not_reveal_inaccessible_records(search_setup):
    search_setup.acl.return_value = None
    result = await azure_search.hybrid_search_detailed("policy")
    assert result == {"results": [], "retrieval_status": "empty"}
    search_setup.embedding.assert_not_awaited()
    search_setup.client.search.assert_not_called()


async def test_semantic_fallback_preserves_acl_and_canonical_check(search_setup):
    source = {"id": "chunk-1", "doc_id": "own-document", "content": "Evidence"}
    search_setup.client.search.side_effect = [RuntimeError("semantic unavailable"), [source]]
    result = await azure_search.hybrid_search_detailed("policy", filter_str="department eq 'Legal'")
    assert result == {"results": [source], "retrieval_status": "ok"}
    for call in search_setup.client.search.call_args_list:
        assert "own-document" in call.kwargs["filter"]
        assert "department eq 'Legal'" in call.kwargs["filter"]
    assert "query_type" not in search_setup.client.search.call_args_list[-1].kwargs
    search_setup.post_filter.assert_called_once_with([source])


async def test_embedding_failure_still_allows_keyword_evidence(search_setup):
    source = {"id": "chunk-1", "doc_id": "own-document", "content": "Evidence"}
    search_setup.client.search.return_value = [source]
    search_setup.embedding.side_effect = RuntimeError("embedding unavailable")
    result = await azure_search.hybrid_search_detailed("policy")
    assert result == {"results": [source], "retrieval_status": "ok"}
    assert "vector_queries" not in search_setup.client.search.call_args.kwargs


async def test_postfilter_failure_never_returns_unverified_index_text(search_setup):
    search_setup.client.search.return_value = [{"content": "unverified private material"}]
    search_setup.post_filter.side_effect = RuntimeError("canonical database unavailable")
    result = await azure_search.hybrid_search_detailed("policy")
    assert result == {"results": [], "retrieval_status": "access_check_failed"}
    assert search_setup.client.search.call_count == 1


async def test_filtered_stale_or_foreign_results_return_empty(search_setup):
    search_setup.client.search.return_value = [{"content": "stale or foreign"}]
    search_setup.post_filter.side_effect = lambda _: []
    assert await azure_search.hybrid_search_detailed("policy") == {
        "results": [], "retrieval_status": "empty",
    }


async def test_legacy_search_api_retains_list_shape(search_setup):
    source = {"id": "chunk-1", "doc_id": "own-document", "content": "Evidence"}
    search_setup.client.search.return_value = [source]
    assert await azure_search.hybrid_search("policy") == [source]
    search_setup.client.search.side_effect = RuntimeError("offline")
    assert await azure_search.hybrid_search("policy") == []


async def test_cancelled_search_is_not_converted_to_a_knowledge_gap(search_setup):
    search_setup.embedding.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await azure_search.hybrid_search_detailed("policy")


@pytest.mark.parametrize("status", ["empty", "unavailable", "access_check_failed"])
async def test_researcher_propagates_safe_status(monkeypatch, status):
    monkeypatch.setattr(researcher, "_CAPS_AVAILABLE", False)
    monkeypatch.setattr(researcher, "hybrid_search_detailed", AsyncMock(return_value={
        "results": [], "retrieval_status": status,
    }))
    result = json.loads(await researcher.ResearcherAgent().search_documents("policy"))
    assert result["results"] == []
    assert result["retrieval_status"] == status
    assert result["knowledge_gap"] is True
    assert "does not have sufficient documents" not in result["message"]


async def test_researcher_does_not_send_denied_search(monkeypatch):
    search = AsyncMock()
    monkeypatch.setattr(researcher, "_CAPS_AVAILABLE", True)
    monkeypatch.setattr(researcher.capability_guard, "require", Mock(side_effect=PermissionError("private details")))
    monkeypatch.setattr(researcher, "hybrid_search_detailed", search)
    result = json.loads(await researcher.ResearcherAgent().search_documents("policy"))
    assert result["retrieval_status"] == "access_check_failed"
    assert "private details" not in json.dumps(result)
    search.assert_not_awaited()


async def test_researcher_success_preserves_provenance(monkeypatch):
    monkeypatch.setattr(researcher, "_CAPS_AVAILABLE", False)
    source = {
        "id": "chunk-1", "doc_id": "own-document", "content": "Evidence",
        "provenance": {"sha256": "test-hash"}, "@search.score": 1,
    }
    monkeypatch.setattr(researcher, "hybrid_search_detailed", AsyncMock(return_value={
        "results": [source], "retrieval_status": "ok",
    }))
    monkeypatch.setattr(researcher, "rerank_results", lambda query, rows, top_n: rows)
    result = json.loads(await researcher.ResearcherAgent().search_documents("policy"))
    assert result["retrieval_status"] == "ok"
    assert result["results"][0]["chunk_id"] == "chunk-1"
    assert result["results"][0]["provenance"] == {"sha256": "test-hash"}


async def test_researcher_unexpected_error_is_sanitized(monkeypatch):
    monkeypatch.setattr(researcher, "_CAPS_AVAILABLE", False)
    monkeypatch.setattr(researcher, "hybrid_search_detailed", AsyncMock(side_effect=RuntimeError("secret token")))
    result = json.loads(await researcher.ResearcherAgent().search_documents("policy"))
    assert result["retrieval_status"] == "unavailable"
    assert "secret token" not in json.dumps(result)
