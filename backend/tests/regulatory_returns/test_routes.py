"""HTTP layer for /api/returns: auth wiring, multipart inputs, file responses."""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.database import get_db
from routes.regulatory_returns import router
from services.auth_utils import get_current_user
from tests.regulatory_returns.test_returns import PROFILE, _prudential_upload


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass


def _client():
    app = FastAPI()
    app.include_router(router)
    session = _FakeSession()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1", role="analyst")
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app), session


def test_catalog_lists_returns_and_calendar():
    client, _ = _client()
    body = client.get("/api/returns/catalog").json()
    ids = {r["id"] for r in body["returns"]}
    assert {"cbn-monthly-prudential", "nfiu-str", "ndpc-compliance-audit"} <= ids
    assert body["calendar"] and body["profile_fields"]


def test_template_download():
    client, _ = _client()
    res = client.get("/api/returns/cbn-monthly-prudential/template")
    assert res.status_code == 200 and res.content[:2] == b"PK"
    assert client.get("/api/returns/cbn-whistleblowing/template").status_code == 404


def test_preview_then_generate_zip_and_audit():
    client, session = _client()
    payload = {"profile": PROFILE, "period": "2026-09", "letter_date": "2026-10-03", "data": {}, "remediation": {}}
    files = {"file": ("input.xlsx", _prudential_upload(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    prev = client.post("/api/returns/cbn-monthly-prudential/preview", data={"payload": json.dumps(payload)}, files=files).json()
    assert prev["remediation_required"][0]["code"] == "SOL"

    blocked = client.post("/api/returns/cbn-monthly-prudential/generate", data={"payload": json.dumps(payload)}, files=files)
    assert blocked.status_code == 422 and blocked.json()["errors"]

    payload["remediation"] = {"SOL": "Exposure to be reduced by repayment before 31 October 2026."}
    res = client.post("/api/returns/cbn-monthly-prudential/generate", data={"payload": json.dumps(payload)}, files=files)
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    assert "AMFB_CBN_MPR_2026-09.zip" in res.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
    assert names == ["AMFB_CBN_MPR_2026-09.docx", "AMFB_CBN_MPR_2026-09.xlsx"]
    assert session.added and session.added[0].action == "regulatory_return_generated"


def test_single_file_return_and_bad_payload():
    client, _ = _client()
    data = {"policy_approval_date": "2024-02-10", "channels": "hotline", "cases_received": 0, "cases_investigated": 0,
            "cases_substantiated": 0, "cases_closed": 0, "cases_pending": 0}
    payload = {"profile": PROFILE, "period": "2026-H1", "data": data}
    res = client.post("/api/returns/cbn-whistleblowing/generate", data={"payload": json.dumps(payload)})
    assert res.status_code == 200 and res.headers["content-disposition"].endswith('.docx"')
    assert client.post("/api/returns/cbn-whistleblowing/preview", data={"payload": "not json"}).status_code == 400
    assert client.post("/api/returns/nope/preview", data={"payload": "{}"}).status_code == 404
    assert client.post("/api/returns/cbn-board-appraisal/preview", data={"payload": "{}"}).status_code == 400
