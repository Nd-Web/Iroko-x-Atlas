"""Security and end-to-end pipeline checks; all cloud adapters are isolated fakes."""

import asyncio
import zipfile
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ingestion.access import Principal, as_user, principal, require_document
from ingestion.api import router as ingestion_router
from ingestion.models import Chunk, DocumentAccess, Membership, Workspace, WorkspaceUsage
from ingestion.pipeline import accept, process, reserve_ocr, review
from ingestion.queue import claim
from ingestion.validation import UploadLimitError, validate_file
from ingestion.workspaces import assign_member, set_shared
from models.database import Document, User, get_db
from services.auth_utils import create_access_token


@pytest.fixture
def users(db):
    owner = db.get(User, "owner")
    owner.organisation = "Same company label"
    stranger = User(
        id="stranger",
        email="stranger@example.invalid",
        hashed_password="unused",
        organisation=owner.organisation,
        role="admin",
    )
    platform = User(
        id="platform", email="platform@example.invalid", hashed_password="unused", role="superadmin"
    )
    db.add_all([stranger, platform])
    db.commit()
    return owner, stranger, platform


@pytest.fixture
def api(db, monkeypatch):
    from routes.documents import router as documents_router

    monkeypatch.setenv("DOCUMENT_PIPELINE_ENABLED", "true")
    app = FastAPI()
    app.include_router(ingestion_router)
    app.include_router(documents_router)
    from routes.alerts import router as alerts_router
    from routes.analytics import router as analytics_router
    from routes.graph import router as graph_router
    from routes.workflows import router as workflows_router

    app.include_router(alerts_router)
    app.include_router(analytics_router)
    app.include_router(graph_router)
    app.include_router(workflows_router)

    def dependency():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as client:
        yield client


def headers(user):
    return {"Authorization": "Bearer " + create_access_token(user.id, user.role)}


def test_login_audit_works_with_migrated_workspace_schema(api, db):
    from ingestion.models import RecordAccess
    from models.database import AuditLog
    from routes.auth import router as auth_router
    from services.auth_utils import hash_password

    api.app.include_router(auth_router)
    owner = db.get(User, "owner")
    owner.email = "owner@example.com"
    owner.full_name = "Test Owner"
    owner.hashed_password = hash_password("regression-only-password")
    db.commit()
    response = api.post("/api/auth/login", json={"email": owner.email, "password": "regression-only-password"})
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]
    assert response.json()["user"]["id"] == owner.id
    audit = db.query(AuditLog).filter_by(action="user_login", user_id=owner.id).one()
    assert db.get(RecordAccess, ("audit", audit.id)).workspace_id == "user:owner"
    denied = api.post("/api/auth/login", json={"email": owner.email, "password": "wrong-password"})
    assert denied.status_code == 401
    assert db.query(AuditLog).filter_by(action="user_login", user_id=owner.id).count() == 1


@pytest.fixture
def retrieval_db(db, monkeypatch):
    @contextmanager
    def session():
        yield db

    monkeypatch.setattr("ingestion.db.Session", session)


async def test_upload_process_evidence_original_and_customer_isolation(
    api, db, users, content, adapters
):
    owner, stranger, platform = users
    response = api.post(
        "/api/documents",
        headers=headers(owner),
        files={"file": ("policy.txt", content.read_bytes(), "text/plain")},
    )
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]
    assert response.json()["status"] == "pending"
    assert db.get(DocumentAccess, doc_id).workspace_id == "user:owner"
    await process(db, *claim(db))
    assert api.get(f"/api/documents/{doc_id}", headers=headers(owner)).json()["status"] == "indexed"
    evidence = api.get(f"/api/ingestion/documents/{doc_id}", headers=headers(owner))
    assert evidence.status_code == 200
    assert evidence.json()["chunks"][0]["content"]
    original = api.get(f"/api/ingestion/documents/{doc_id}/original", headers=headers(owner))
    assert original.content == content.read_bytes()
    for other in [stranger, platform]:
        for path in [
            f"/api/documents/{doc_id}",
            f"/api/ingestion/documents/{doc_id}",
            f"/api/ingestion/documents/{doc_id}/original",
        ]:
            assert api.get(path, headers=headers(other)).status_code == 404
        for suffix in ["reindex", "reprocess"]:
            assert (
                api.post(
                    f"/api/ingestion/documents/{doc_id}/{suffix}", headers=headers(other)
                ).status_code
                == 404
            )
        assert api.delete(f"/api/documents/{doc_id}", headers=headers(other)).status_code == 404
        assert api.get("/api/documents", headers=headers(other)).json()["total"] == 0
        assert (
            api.get("/api/documents/analytics", headers=headers(other)).json()["total_documents"]
            == 0
        )
        assert api.get("/api/ingestion/stats", headers=headers(other)).json()["jobs"] == {}
    assert api.get(f"/api/documents/{doc_id}").status_code == 401
    assert principal.get() is None


async def test_derived_alerts_graph_audit_and_gaps_do_not_leak(api, db, users, content, adapters):
    from models.database import AgentRun, Alert, AuditLog, KnowledgeGap
    from models.workflow import WorkflowTask

    owner, stranger, _ = users
    doc = await accept(
        db,
        content,
        "policy.txt",
        "PRIVATE REGULATORY TITLE",
        owner.id,
        {"regulator": "CBN", "source_url": "https://www.cbn.gov.ng/Out/test.pdf"},
    )
    await process(db, *claim(db))
    review(db, doc.id, owner.id, "approve", "Reviewed exact source text")
    await process(db, *claim(db))
    with as_user(owner):
        db.add(KnowledgeGap(id="private-gap", query="PRIVATE QUERY DETAIL"))
        db.add(
            AgentRun(id="private-run", agent_type="strategist", input_query="PRIVATE QUERY DETAIL")
        )
        db.add(WorkflowTask(id="private-task", title="PRIVATE FOLLOWUP", created_by_id=owner.id))
        db.commit()
    for path in [
        "/api/graph",
        "/api/alerts?status=all",
        "/api/analytics/activity",
        "/api/analytics/knowledge-gaps",
        "/api/analytics/stats",
        "/api/workflows/tasks",
    ]:
        response = api.get(path, headers=headers(stranger))
        assert response.status_code == 200, response.text
        assert "PRIVATE" not in response.text
        assert doc.id not in response.text
        assert "private-task" not in response.text
    assert "PRIVATE REGULATORY TITLE" in api.get("/api/graph", headers=headers(owner)).text
    assert (
        "PRIVATE REGULATORY TITLE" in api.get("/api/alerts?status=all", headers=headers(owner)).text
    )
    assert (
        "PRIVATE QUERY DETAIL"
        in api.get("/api/analytics/knowledge-gaps", headers=headers(owner)).text
    )
    alert_id = f"ingestion-{doc.id}"
    for suffix in ["acknowledge", "resolve"]:
        assert (
            api.patch(f"/api/alerts/{alert_id}/{suffix}", headers=headers(stranger)).status_code
            == 404
        )
    assert (
        api.post(f"/api/alerts/{alert_id}/draft-response", headers=headers(stranger)).status_code
        == 404
    )
    assert (
        api.patch(
            "/api/workflows/tasks/private-task", headers=headers(stranger), json={"status": "done"}
        ).status_code
        == 404
    )
    # Unknown legacy rows must remain hidden even when the organisation label matches.
    db.add(
        Alert(
            id="legacy-unowned",
            title="PRIVATE LEGACY",
            summary="Unattributed",
            alert_type="general",
            organisation=owner.organisation,
        )
    )
    db.add(AuditLog(action="unowned", resource="unowned", details={"text": "PRIVATE LEGACY"}))
    db.commit()
    assert "PRIVATE LEGACY" not in api.get("/api/alerts?status=all", headers=headers(owner)).text
    assert "PRIVATE LEGACY" not in api.get("/api/analytics/activity", headers=headers(owner)).text


def test_alert_refresh_creates_separate_workspace_records(api, db, users, monkeypatch):
    owner, stranger, _ = users
    monkeypatch.setattr(
        "agents.watchdog.WatchdogAgent.run_all_checks",
        AsyncMock(
            return_value='{"alerts": [{"title": "Same finding", "summary": "Private evidence", "severity": "warning"}]}'
        ),
    )
    for user in [owner, stranger]:
        response = api.post("/api/alerts/refresh", headers=headers(user))
        assert response.status_code == 200, response.text
        assert response.json()["created"] == 1
        assert api.get("/api/alerts?status=all", headers=headers(user)).json()["total"] == 1


async def test_shared_documents_require_explicit_platform_action(db, users, content, adapters):
    owner, stranger, platform = users
    doc = await accept(
        db,
        content,
        "circular.txt",
        "Circular",
        platform.id,
        {"regulator": "CBN", "source_url": "https://www.cbn.gov.ng/Out/test.pdf"},
    )
    await process(db, *claim(db))
    review(db, doc.id, platform.id, "approve", "Checked public source and extraction")
    await process(db, *claim(db))
    with pytest.raises(HTTPException):
        set_shared(db, owner, doc.id, True, "Verified public source")
    set_shared(db, platform, doc.id, True, "Verified public source")
    assert require_document(db, doc.id, stranger).id == doc.id
    with pytest.raises(HTTPException):
        require_document(db, doc.id, stranger, write=True)
    set_shared(db, platform, doc.id, False, "Remove public visibility")
    with pytest.raises(HTTPException):
        require_document(db, doc.id, stranger)


async def test_workspace_assignment_is_explicit_and_existing_documents_cannot_be_moved(
    db, users, content, adapters
):
    owner, stranger, platform = users
    db.add(Workspace(id="customer-a", name="Customer A"))
    db.commit()
    assign_member(db, platform, owner.id, "customer-a")
    assign_member(db, platform, stranger.id, "customer-a")
    doc = await accept(db, content, "policy.txt", "Policy", owner.id)
    assert require_document(db, doc.id, stranger).id == doc.id
    db.add(Workspace(id="customer-b", name="Customer B"))
    db.commit()
    with pytest.raises(HTTPException) as error:
        assign_member(db, platform, owner.id, "customer-b")
    assert error.value.status_code == 409
    assert db.get(Membership, owner.id).workspace_id == "customer-a"


async def test_search_prefilter_postfilter_and_no_principal_fail_closed(
    db, users, content, adapters, retrieval_db, monkeypatch
):
    from services import azure_search

    owner, stranger, _ = users
    first = await accept(db, content, "policy.txt", "Private A", owner.id)
    await process(db, *claim(db))
    second = await accept(db, content, "policy.txt", "Private B", stranger.id)
    await process(db, *claim(db))
    hits = [{"id": c.id, "doc_id": c.document_id, "content": c.content} for c in db.query(Chunk)]
    captured = []

    def search(**kwargs):
        captured.append(kwargs)
        return hits  # Deliberately simulate a misbehaving or stale search index.

    monkeypatch.setattr(azure_search, "get_search_client", lambda: SimpleNamespace(search=search))
    embedding = AsyncMock(return_value=None)
    monkeypatch.setattr("services.embeddings.get_embedding", embedding)
    assert await azure_search.hybrid_search("policy") == []
    embedding.assert_not_awaited()
    with as_user(owner):
        results = await azure_search.hybrid_search("policy", filter_str="department eq 'Legal'")
        assert {r["doc_id"] for r in results} == {first.id}
        assert first.id in captured[0]["filter"] and second.id not in captured[0]["filter"]
        assert "department eq 'Legal'" in captured[0]["filter"]
        assert (
            azure_search.eligible_results(
                [{"id": "foreign", "doc_id": "unknown", "content": "secret"}]
            )
            == []
        )
        assert azure_search.eligible_results([{**results[0], "content": "stale text"}]) == []
    assert principal.get() is None


async def test_principal_context_isolated_between_concurrent_tasks():
    async def task(user_id):
        with as_user(Principal(user_id, "admin")):
            await asyncio.sleep(0)
            return principal.get().id

    assert await asyncio.gather(task("a"), task("b")) == ["a", "b"]
    assert principal.get() is None


async def test_stream_binds_identity_after_request_dependency_cleanup():
    from routes.ask import _scoped_stream

    async def body():
        await asyncio.sleep(0)
        yield principal.get().id

    assert principal.get() is None
    assert [item async for item in _scoped_stream(body(), Principal("stream-user", "admin"))] == [
        "stream-user"
    ]
    assert principal.get() is None


async def test_upload_quota_duplicate_is_free_and_failure_rolls_back(
    db, content, adapters, monkeypatch
):
    monkeypatch.setenv("WORKSPACE_DAILY_UPLOAD_LIMIT", "1")
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    assert (await accept(db, content, "policy.txt", "Policy", "owner")).id == doc.id
    with pytest.raises(UploadLimitError):
        await accept(db, content, "second.txt", "Second", "owner")
    db.rollback()
    assert db.query(Document).count() == 1
    assert db.query(WorkspaceUsage).one().uploads == 1


def test_workspace_ocr_budget_is_separate_from_global_budget(db, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DAILY_OCR_PAGES", "2")
    monkeypatch.setenv("DOCINTEL_DAILY_PAGE_BUDGET", "5")
    assert reserve_ocr(db, 4, "workspace-a") == 2
    assert reserve_ocr(db, 1, "workspace-a") == 0
    assert reserve_ocr(db, 4, "workspace-b") == 2
    assert reserve_ocr(db, 4, "workspace-c") == 1


@pytest.mark.parametrize(
    "body,name",
    [
        (b"<html>Denied</html>", "scan.pdf"),
        (b"%PDF-1.7 truncated", "scan.pdf"),
        (b"binary\x00text", "policy.txt"),
        (b"\xff\xfe", "policy.txt"),
    ],
)
def test_disguised_or_malformed_files_rejected(tmp_path, body, name):
    path = tmp_path / name
    path.write_bytes(body)
    with pytest.raises(ValueError):
        validate_file(path, name)


@pytest.mark.parametrize(
    "member,body",
    [
        ("../escape.xml", b"text"),
        ("word/document.xml", b'<!DOCTYPE x [<!ENTITY e "boom">]>'),
        ("word/vbaProject.bin", b"macro"),
        ("word/embeddings/object.bin", b"embedded"),
    ],
)
def test_hostile_office_archives_rejected(tmp_path, member, body):
    path = tmp_path / "policy.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        if member != "word/document.xml":
            archive.writestr("word/document.xml", "<document/>")
        archive.writestr(member, body)
    with pytest.raises(ValueError):
        validate_file(path, path.name)


def test_parser_subprocess_timeout_is_bounded(tmp_path, monkeypatch):
    import subprocess

    from ingestion.extraction import bounded_native_pages

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 150
        assert "AZURE_SEARCH_KEY" not in kwargs["env"]
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setenv("AZURE_SEARCH_KEY", "never-send-to-parser")
    monkeypatch.setattr("ingestion.extraction.subprocess.run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        bounded_native_pages(tmp_path / "file.pdf", "pdf")


async def test_scheduled_drain_schedules_once_and_idles_successfully(monkeypatch):
    from ingestion.batch import drain

    worker = AsyncMock(return_value=False)
    scheduled = []
    monkeypatch.setattr("ingestion.batch.run_once", worker)
    monkeypatch.setattr("ingestion.batch._schedule_due_sources", lambda: scheduled.append(1))
    monkeypatch.setattr("ingestion.batch._snapshot", lambda: {})
    monkeypatch.setattr("ingestion.batch._status", lambda *_: (0, [], []))
    assert (await drain(allow_idle=True))["processed_jobs"] == 0
    # Due recurring sources are queued once per execution, not on every claim.
    assert scheduled == [1]
    worker.assert_awaited_once_with(include_scheduled=False)


async def test_scheduled_drain_yields_delayed_retries_instead_of_waiting(monkeypatch):
    from ingestion.batch import drain

    monkeypatch.setattr("ingestion.batch.run_once", AsyncMock(return_value=False))
    monkeypatch.setattr("ingestion.batch._schedule_due_sources", lambda: None)
    monkeypatch.setattr("ingestion.batch._snapshot", lambda: {})
    monkeypatch.setattr("ingestion.batch._status", lambda *_: (3, [], []))
    assert (await drain(allow_idle=True))["pending_jobs"] == 3


async def test_scheduled_drain_reports_blocked_source_without_failing(monkeypatch):
    from ingestion.batch import BatchIncomplete, drain

    blocked = [{"source_id": "cbn", "status": "blocked", "found": 9, "accepted": 0,
                "errors": [{"error": "AccessChallenge"}]}]
    monkeypatch.setattr("ingestion.batch.run_once", AsyncMock(return_value=False))
    monkeypatch.setattr("ingestion.batch._schedule_due_sources", lambda: None)
    monkeypatch.setattr("ingestion.batch._snapshot", lambda: {})
    monkeypatch.setattr("ingestion.batch._status", lambda *_: (0, [], blocked))
    assert (await drain(allow_idle=True))["source_results"] == blocked
    # A newly exhausted job still fails a scheduled execution visibly.
    monkeypatch.setattr("ingestion.batch._status", lambda *_: (0, ["document:x"], blocked))
    with pytest.raises(BatchIncomplete, match="1 failed jobs"):
        await drain(allow_idle=True)


def test_upload_body_limit_covers_missing_content_length():
    from fastapi import File, UploadFile

    from ingestion.http_limits import DocumentBodyLimit

    app = FastAPI()
    app.add_middleware(DocumentBodyLimit, max_bytes=100)

    @app.post("/api/documents")
    async def upload(file: UploadFile = File(...)):
        return {"size": len(await file.read())}

    with TestClient(app) as client:
        assert client.post("/api/documents", content=b"x" * 101).status_code == 413

        def oversized():
            yield b'--test\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n\r\n'
            yield b"x" * 101
            yield b"\r\n--test--\r\n"

        assert (
            client.post(
                "/api/documents",
                content=oversized(),
                headers={"Content-Type": "multipart/form-data; boundary=test"},
            ).status_code
            == 413
        )


async def test_archive_hides_document_and_disabled_pipeline_refuses_hard_delete(
    api, db, users, content, adapters, monkeypatch
):
    owner, _, _ = users
    response = api.post(
        "/api/documents",
        headers=headers(owner),
        files={"file": ("policy.txt", content.read_bytes(), "text/plain")},
    )
    doc_id = response.json()["id"]
    await process(db, *claim(db))

    monkeypatch.setenv("DOCUMENT_PIPELINE_ENABLED", "false")
    refused = api.delete(f"/api/documents/{doc_id}", headers=headers(owner))
    assert refused.status_code == 503
    assert db.get(Document, doc_id).status == "indexed"
    original = api.get(f"/api/ingestion/documents/{doc_id}/original", headers=headers(owner))
    assert original.content == content.read_bytes()

    monkeypatch.setenv("DOCUMENT_PIPELINE_ENABLED", "true")
    assert api.delete(f"/api/documents/{doc_id}", headers=headers(owner)).status_code == 200
    assert db.get(Document, doc_id).status == "archived"
    assert api.get("/api/documents", headers=headers(owner)).json()["total"] == 0
    archived = api.get("/api/documents?status=archived", headers=headers(owner)).json()
    assert [d["id"] for d in archived["documents"]] == [doc_id]
