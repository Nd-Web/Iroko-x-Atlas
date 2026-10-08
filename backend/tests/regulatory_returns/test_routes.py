"""HTTP layer for /api/returns: auth wiring, multipart inputs, file responses."""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.database import AuditLog, get_db
from routes.regulatory_returns import router
from services.auth_utils import get_current_user
from tests.regulatory_returns.test_returns import PROFILE, _prudential_upload


@pytest.fixture
def client(db, user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_catalog_lists_returns_and_calendar(client):
    body = client.get("/api/returns/catalog").json()
    ids = {r["id"] for r in body["returns"]}
    assert {"cbn-monthly-prudential", "nfiu-str", "ndpc-compliance-audit"} <= ids
    assert body["calendar"] and body["profile_fields"]
    assert all(item["status"] == "not_started" for item in body["calendar"])
    assert next(r for r in body["returns"] if r["id"] == "cbn-monthly-prudential")["datasets"][0]["kind"] == "trial_balance"


def test_template_download(client):
    res = client.get("/api/returns/cbn-monthly-prudential/template")
    assert res.status_code == 200 and res.content[:2] == b"PK"
    assert client.get("/api/returns/cbn-whistleblowing/template").status_code == 404


def test_preview_then_generate_zip_and_audit(client, db):
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
    assert db.query(AuditLog).filter_by(action="regulatory_return_generated").count() == 1


def test_single_file_return_and_bad_payload(client):
    data = {"policy_approval_date": "2024-02-10", "channels": "hotline", "cases_received": 0, "cases_investigated": 0,
            "cases_substantiated": 0, "cases_closed": 0, "cases_pending": 0}
    payload = {"profile": PROFILE, "period": "2026-H1", "data": data}
    res = client.post("/api/returns/cbn-whistleblowing/generate", data={"payload": json.dumps(payload)})
    assert res.status_code == 200 and res.headers["content-disposition"].endswith('.docx"')
    assert client.post("/api/returns/cbn-whistleblowing/preview", data={"payload": "not json"}).status_code == 400
    assert client.post("/api/returns/nope/preview", data={"payload": "{}"}).status_code == 404
    assert client.post("/api/returns/cbn-board-appraisal/preview", data={"payload": "{}"}).status_code == 400
