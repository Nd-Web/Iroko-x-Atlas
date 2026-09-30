from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ingestion.api import router
from ingestion.extraction import ocr_pages
from ingestion.migrations.ownership import include_name, include_object
from ingestion.models import Revision
from ingestion.sources import OfficialClient
from models.database import Document
from services.auth_utils import get_current_user


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="viewer", role="viewer")
    return TestClient(app)


def test_non_admin_cannot_review_or_configure_sources(client):
    assert (
        client.post(
            "/api/ingestion/documents/unknown/review",
            json={"decision": "approve", "note": "Approve"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/ingestion/sources",
            json={"regulator": "CBN", "url": "https://www.cbn.gov.ng/", "parser": "cbn_json"},
        ).status_code
        == 403
    )


def test_migration_filters_reject_other_and_unresolved_schemas():
    assert include_object(Revision.__table__, "", "table", False, None)
    assert not include_object(Document.__table__, "", "table", False, None)
    assert not include_object(Revision.__table__.c.id, "", "column", False, Document.__table__.c.id)
    assert not include_object(object(), "", "index", True, None)
    assert include_name("ingestion", "schema", {})
    assert not include_name(None, "schema", {})
    assert not include_name("table", "table", {"schema_name": "public"})


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setattr(
        "ingestion.sources.socket.getaddrinfo",
        lambda *a, **kw: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    monkeypatch.setattr("ingestion.sources.asyncio.sleep", AsyncMock())


async def test_redirect_cannot_escape_allowlist(http):
    source = OfficialClient("CBN")
    source.client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: (
                httpx.Response(200, text="User-agent: *\nAllow: /")
                if request.url.path == "/robots.txt"
                else httpx.Response(302, headers={"Location": "https://evil.test/internal"})
            )
        )
    )
    try:
        with pytest.raises(ValueError, match="approved"):
            await source.fetch("https://www.cbn.gov.ng/file.pdf")
    finally:
        await source.close()


async def test_robots_errors_fail_closed_and_403_is_not_retried(http):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(403, text="Forbidden")

    source = OfficialClient("CBN")
    source.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await source.fetch("https://www.cbn.gov.ng/file.pdf")
        assert calls == ["/robots.txt"]
    finally:
        await source.close()


async def test_size_limit_applies_to_streamed_body(http):
    source = OfficialClient("CBN")
    source.client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 20))
    )
    try:
        with pytest.raises(ValueError, match="limit"):
            await source._request("https://www.cbn.gov.ng/file.pdf", cap=10)
    finally:
        await source.close()


def test_ocr_requests_only_flagged_pages_and_preserves_unicode_offsets(monkeypatch, tmp_path):
    captured = {}

    class FakeClient:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def begin_analyze_document(self, model, **kwargs):
            captured.update(kwargs)
            assert model == "prebuilt-layout"
            return SimpleNamespace(
                result=lambda timeout: SimpleNamespace(
                    content="₦42 table",
                    pages=[
                        SimpleNamespace(
                            page_number=3,
                            spans=[SimpleNamespace(offset=0, length=9)],
                            words=[SimpleNamespace(confidence=0.99)],
                        )
                    ],
                )
            )

    monkeypatch.setattr("azure.ai.documentintelligence.DocumentIntelligenceClient", FakeClient)
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "test-key")
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF- fake test bytes")
    result = ocr_pages(path, [3])
    assert captured["pages"] == "3"
    assert captured["string_index_type"] == "unicodeCodePoint"
    assert result[3]["text"] == "₦42 table"
