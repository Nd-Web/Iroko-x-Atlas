"""The filing assistant end to end: Iroko fills what it can, asks for the rest."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

import routes.regulatory_returns as returns_routes
from models.database import get_db
from services.auth_utils import get_current_user
from tests.regulatory_returns.test_returns import PROFILE

# ─── Fakes for the model and the document search ─────────────────────────────

AI_LINES = {"1006": "A06"}


async def fake_complete(prompt: str, **kwargs) -> str:
    schema = kwargs.get("json_schema") or {}
    props = schema.get("properties", {})
    if "mappings" in props:
        return json.dumps({"mappings": [{"code": c, "line": l} for c, l in AI_LINES.items() if f"\n{c} |" in prompt or prompt.startswith(c)]})
    if "answers" in props:
        return json.dumps({"answers": [
            {"key": "policy_approval_date", "found": True, "value": "2024-02-10",
             "quote": "This Whistle-blowing Policy was approved by the Board of Directors on 10 February 2024.", "document_id": "doc-1"},
            {"key": "channels", "found": True, "value": "whistle@adire.test and the 0700 hotline",
             "quote": "Concerns may be raised in confidence at whistle@adire.test or via the hotline that does not exist", "document_id": "doc-1"},
        ]})
    if "columns" in props:
        return json.dumps({"columns": []})
    return "The Bank will reduce the exposure through scheduled repayments approved by the Board Credit Committee by 30 November 2026."


async def fake_retrieve(question: str) -> dict:
    return {"sources": [{
        "document_id": "doc-1", "title": "Whistle-blowing Policy 2024",
        "content": "WHISTLE-BLOWING POLICY. This Whistle-blowing Policy was approved by the Board of Directors on 10 February 2024. "
                   "Concerns may be raised in confidence at whistle@adire.test or by calling 0700-ADIRE.",
    }]}


@pytest.fixture
def client(db, user, monkeypatch):
    monkeypatch.setattr(returns_routes, "_complete", fake_complete)
    monkeypatch.setattr(returns_routes, "_retrieve", fake_retrieve)
    app = FastAPI()
    app.include_router(returns_routes.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    assert c.put("/api/returns/profile", json=PROFILE).json()["missing"] == []
    return c


def _open(client, return_id, period=None):
    res = client.post("/api/returns/drafts", json={"return_id": return_id, "period": period})
    assert res.status_code == 200, res.text
    return res.json()


def _patch(client, draft_id, **body):
    res = client.patch(f"/api/returns/drafts/{draft_id}", json=body)
    assert res.status_code == 200, res.text
    return res.json()


# ─── Core banking exports, in their own layouts ──────────────────────────────

TB = [  # GL code, description, debit, credit — balanced; mirrors the SFP/PL fixture in test_returns
    ("1001", "Cash in Vault - Head Office", 45e6, 0), ("1002", "Balance with CBN", 120e6, 0),
    ("1003", "Zenith Bank - Settlement", 210e6, 0), ("1004", "Placement with Access Bank (30 days)", 150e6, 0),
    ("1005", "Treasury Bills", 300e6, 0), ("1006", "Equity investment - unquoted", 50e6, 0),
    ("1101", "Microloans - Individual", 1200e6, 0), ("1102", "SME Loans", 400e6, 0),
    ("1201", "Provision for loan impairment", 0, 40e6), ("1301", "Prepayments", 100e6, 0),
    ("1302", "Other receivables", 175e6, 0), ("1401", "Motor vehicles", 120e6, 0), ("1402", "Office equipment", 100e6, 0),
    ("1403", "Accumulated depreciation", 0, 40e6), ("1501", "Software", 20e6, 0),
    ("2001", "Current accounts", 0, 420e6), ("2002", "Savings deposits", 0, 610e6), ("2003", "Fixed deposits", 0, 380e6),
    ("2004", "Mandatory savings", 0, 40e6), ("2101", "Interbank takings", 0, 60e6),
    ("2102", "CBN MSMEDF on-lending facility", 0, 80e6), ("2201", "Income tax payable", 0, 12e6),
    ("2301", "Accrued expenses", 0, 30e6), ("2302", "Sundry creditors", 0, 18e6),
    ("3001", "Share capital", 0, 1000e6), ("3002", "Share premium", 0, 50e6), ("3003", "Statutory reserve", 0, 90e6),
    ("3004", "Retained earnings b/f", 0, 65e6),
    ("4001", "Interest income on loans", 0, 310e6), ("4002", "Interest income - treasury bills", 0, 42e6),
    ("4101", "Fees and commission", 0, 38e6), ("4201", "Recoveries", 0, 6e6),
    ("5001", "Interest expense on savings deposits", 95e6, 0), ("5002", "Interest on borrowings", 9e6, 0),
    ("5101", "Loan impairment charge", 22e6, 0), ("5201", "Salaries and wages", 110e6, 0), ("5301", "Depreciation", 18e6, 0),
    ("5401", "Rent and utilities", 30e6, 0), ("5402", "Diesel and generator", 14e6, 0), ("5403", "Audit fees", 5e6, 0),
    ("5404", "Advertising", 15e6, 0), ("5501", "Company income tax charge", 23e6, 0),
]


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def trial_balance_file() -> bytes:
    rows = [["Adire MFB Ltd — Trial Balance as at 30 Sep 2026"], [], ["GL Code", "Account Description", "Debit (NGN)", "Credit (NGN)"]]
    rows += [[c, n, d or None, cr or None] for c, n, d, cr in TB]
    rows.append(["", "TOTAL", sum(r[2] for r in TB), sum(r[3] for r in TB)])
    return _xlsx(rows)


def loan_book_csv() -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Customer No", "Customer Name", "Product", "Loan Balance", "Days in Arrears", "Branch"])
    w.writerow(["B001", "Okon Traders Cooperative Society", "Group loan", "60,000,000.00", 0, "Ikeja"])
    w.writerow(["B002", "Amina Bello", "Personal", "15,000,000.00", 12, "Yaba"])
    w.writerow(["B003", "Tunde Bakare", "Personal", "8,000,000.00", 70, "Yaba"])
    w.writerow(["B004", "Ngozi Eze", "Personal", "2,000,000.00", 200, "Ikeja"])
    for i in range(400):
        w.writerow([f"C{i:04d}", f"Customer {i}", "Micro", f"{1_515_000_000 / 400:.2f}", 45 if i % 10 == 0 else 0, "Yaba"])
    return buf.getvalue().encode()


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_profile_is_shared_and_required(client):
    assert client.get("/api/returns/profile").json()["profile"]["institution_name"] == PROFILE["institution_name"]


def test_fraud_nil_return_in_one_answer(client):
    s = _open(client, "cbn-fraud-forgeries", "2026-09")
    assert [q["key"] for q in s["questions"]] == ["nil_return"]
    assert s["questions"][0]["quick"][0] == {"label": "No — file a nil return", "value": True}
    s = _patch(client, s["draft"]["id"], answers={"nil_return": True})
    assert s["questions"] == [] and s["ready"], s["blocking"]
    res = client.post(f"/api/returns/drafts/{s['draft']['id']}/generate")
    assert res.status_code == 200 and res.headers["content-disposition"].endswith('.docx"')


def test_whistleblowing_from_documents_and_zero_cases(client):
    s = _open(client, "cbn-whistleblowing", "2026-H1")
    did = s["draft"]["id"]
    found = client.post(f"/api/returns/drafts/{did}/find").json()
    # the policy date has a verbatim quote; the channels "quote" is not in the document, so it is rejected
    assert found["found"] == 1
    item = next(i for i in found["items"] if i["key"] == "policy_approval_date")
    assert item["source"]["kind"] == "document" and not item["source"]["confirmed"] and "10 February 2024" in item["source"]["quote"]
    assert "channels" in [q["key"] for q in found["questions"]]
    s = _patch(client, did, answers={"channels": "whistle@adire.test; 0700-ADIRE", "policy_on_website": True, "cases_received": 0})
    # nothing received → the follow-up counts are filled with 0 and not asked
    assert [q["key"] for q in s["questions"]] == []
    assert "Confirm 1 answer" in " ".join(s["blocking"])
    s = _patch(client, did, confirm=["policy_approval_date"])
    assert s["ready"], s["blocking"]
    assert client.post(f"/api/returns/drafts/{did}/generate").status_code == 200

    # next half-year starts from what was filed, awaiting confirmation
    s2 = _open(client, "cbn-whistleblowing", "2026-H2")
    carried = {i["key"]: i["source"] for i in s2["items"]}
    assert carried["policy_approval_date"]["kind"] == "memory"
    assert carried["policy_on_website"]["kind"] == "carried" and "Half-year ended 30 June 2026" in carried["policy_on_website"]["label"]
    assert [q["key"] for q in s2["questions"]] == ["cases_received"]


def test_prudential_from_core_banking_exports(client, db):
    s = _open(client, "cbn-monthly-prudential", "2026-09")
    did = s["draft"]["id"]
    assert [d["status"] for d in s["datasets"]] == ["missing", "missing"]

    s = client.post(f"/api/returns/drafts/{did}/import/trial_balance", files={"file": ("TB_Sept.xlsx", trial_balance_file())}).json()
    tb = s["datasets"][0]
    assert tb["status"] == "needs_review" and tb["unmapped"] == 0 and tb["ai_mapped"] == 1
    hows = {a["code"]: a["how"] for a in tb["accounts"]}
    # bank-named and borrowing-interest accounts are matched by rule; the model only sees the rest
    assert hows["1001"] == hows["1003"] == hows["5002"] == "Accounting rule" and hows["1006"].startswith("Iroko AI")
    assert "Current-year profit of ₦55,000,000.00" in " ".join(tb["notes"])

    s = client.post(f"/api/returns/drafts/{did}/review/trial_balance", json={"confirm": True}).json()
    assert s["datasets"][0]["status"] == "ready"

    s = client.post(f"/api/returns/drafts/{did}/import/loan_book", files={"file": ("loans.csv", loan_book_csv())}).json()
    lb = s["datasets"][1]
    assert lb["status"] == "needs_review" and lb["count"] == 404
    assert any("cooperative" in n.lower() for n in lb["notes"])
    s = client.post(f"/api/returns/drafts/{did}/review/loan_book", json={"confirm": True}).json()
    check = s["check"]
    assert check and check["errors"] == []
    figures = {f["label"]: f["value"] for f in check["figures"]}
    assert figures["Total assets"] == "₦2,910,000,000.00" and figures["Liquidity ratio"] == "56.90%"
    assert [r["code"] for r in check["remediation_required"]] == ["SOL"]

    sug = client.post(f"/api/returns/drafts/{did}/suggest", json={"code": "SOL"}).json()
    assert sug["suggestion"].startswith("The Bank will")
    s = _patch(client, did, remediation={"SOL": sug["suggestion"]})
    assert s["ready"], s["blocking"]
    res = client.post(f"/api/returns/drafts/{did}/generate")
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"

    # next month the same export maps entirely from memory
    s = _open(client, "cbn-monthly-prudential", "2026-10")
    s = client.post(f"/api/returns/drafts/{s['draft']['id']}/import/trial_balance", files={"file": ("TB_Oct.xlsx", trial_balance_file())}).json()
    assert {a["how"] for a in s["datasets"][0]["accounts"]} == {"Your mapping from a previous month"}

    # and the NDIC return for the year picks up December deposits from the monthly return
    dec = _open(client, "cbn-monthly-prudential", "2026-12")
    client.post(f"/api/returns/drafts/{dec['draft']['id']}/import/trial_balance", files={"file": ("TB_Dec.xlsx", trial_balance_file())})
    ndic = _open(client, "ndic-deposit-certification", "2026")
    derived = {i["key"]: i for i in ndic["items"]}
    assert derived["savings_deposits"]["value"] == 610e6 and derived["savings_deposits"]["source"]["kind"] == "derived"


def test_board_carries_forward_and_flags_insider_loans(client):
    board = [
        {"name": "Adebayo Ogun", "role": "Chairman", "first_appointed": "2019-05-01", "cbn_approved": True, "board_meetings_held": 3, "board_meetings_attended": 3, "committees": ""},
        {"name": "Folake Adeyemi", "role": "MD/CEO", "first_appointed": "2020-01-15", "cbn_approved": True, "board_meetings_held": 3, "board_meetings_attended": 3, "committees": "Credit"},
        {"name": "Kemi Lawal", "role": "Independent Non-Executive Director", "first_appointed": "2022-03-01", "cbn_approved": True, "board_meetings_held": 3, "board_meetings_attended": 3, "committees": "Audit"},
        {"name": "Tunde Bakare", "role": "Non-Executive Director", "first_appointed": "2019-05-01", "cbn_approved": True, "board_meetings_held": 3, "board_meetings_attended": 3, "committees": "Audit"},
        {"name": "Grace Nwosu", "role": "Non-Executive Director", "first_appointed": "2021-07-01", "cbn_approved": True, "board_meetings_held": 3, "board_meetings_attended": 3, "committees": "Audit, Credit"},
    ]
    committees = [
        {"name": "Board Risk & Audit Committee (combined)", "chair": "Kemi Lawal", "chair_role": "Independent Non-Executive Director", "members": 3, "meetings_held": 2, "charter_cbn_approved": True},
        {"name": "Board Governance & Nominations Committee", "chair": "Kemi Lawal", "chair_role": "Independent Non-Executive Director", "members": 3, "meetings_held": 2, "charter_cbn_approved": True},
        {"name": "Board Credit Committee", "chair": "Grace Nwosu", "chair_role": "Non-Executive Director", "members": 3, "meetings_held": 2, "charter_cbn_approved": True},
    ]
    s = _open(client, "cbn-cg-compliance", "2026-H1")
    s = _patch(client, s["draft"]["id"], answers={
        "board": board, "committees": committees, "board_meetings_in_period": 3, "external_auditor": "Okoro & Co",
        "external_auditor_cbn_approved": True, "risk_officer_in_place": True, "internal_auditor_in_place": True,
        "board_appraisal_date": "2026-03-20", "family_members_on_board": False,
    })
    assert s["ready"], s["blocking"]
    assert client.post(f"/api/returns/drafts/{s['draft']['id']}/generate").status_code == 200

    s2 = _open(client, "cbn-cg-compliance", "2026-H2")
    carried = next(i for i in s2["items"] if i["key"] == "board")
    assert carried["source"]["kind"] == "memory" and carried["value"][0]["board_meetings_held"] == ""

    # a loan to a director is recognised from the board list
    p = _open(client, "cbn-monthly-prudential", "2026-09")
    s = client.post(f"/api/returns/drafts/{p['draft']['id']}/import/loan_book", files={"file": ("loans.csv", loan_book_csv())}).json()
    lb = s["datasets"][1]
    assert any("Tunde Bakare" in n for n in lb["notes"])
    assert next(l for l in lb["review"] if l["borrower_name"] == "Tunde Bakare")["insider"] is True

    # AFS and NDIC take the auditor from memory
    afs = _open(client, "cbn-afs-submission", "2026")
    assert next(i for i in afs["items"] if i["key"] == "auditor_name")["value"] == "Okoro & Co"


def test_ctr_from_any_layout_and_submission_tracking(client):
    today = date.today()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Value Date", "Account Name", "Account No", "Tran Type", "Amount", "Branch"])
    w.writerow([(today - timedelta(days=2)).strftime("%d/%m/%Y"), "Ada Obi", "0012345678", "Cash deposit", "6,250,000.00", "Yaba"])
    w.writerow([(today - timedelta(days=3)).strftime("%d/%m/%Y"), "Zenon Trading Ltd", "0023456789", "Cash withdrawal", "9,000,000.00", "Ikeja"])
    w.writerow([(today - timedelta(days=4)).strftime("%d-%b-%Y").upper(), "Zenon Trading Ltd", "0023456789", "Cash deposit", "14,500,000.00", "Ikeja"])
    s = _open(client, "nfiu-ctr")
    did = s["draft"]["id"]
    assert {i["key"] for i in s["items"]} >= {"period_from", "period_to", "reporting_officer"}
    s = client.post(f"/api/returns/drafts/{did}/import/transactions", files={"file": ("cash.csv", buf.getvalue().encode())}).json()
    assert s["datasets"][0]["status"] == "ready" and s["datasets"][0]["count"] == 3
    s = _patch(client, did, confirm=[i["key"] for i in s["items"]])
    assert s["ready"], s["blocking"]
    figures = {f["label"]: f["value"] for f in s["check"]["figures"]}
    assert figures["Reportable"] == "2"  # ₦9m to a company is below the ₦10m threshold
    assert client.post(f"/api/returns/drafts/{did}/submitted", json={"submission_ref": "X"}).status_code == 409
    assert client.post(f"/api/returns/drafts/{did}/generate").status_code == 200
    s = client.post(f"/api/returns/drafts/{did}/submitted", json={"submission_ref": "goAML-CTR-88123"}).json()
    assert s["draft"]["status"] == "submitted" and s["draft"]["submission_ref"] == "goAML-CTR-88123"
    assert client.get("/api/returns/events/nfiu-ctr").json()["drafts"][0]["status"] == "submitted"


def test_calendar_shows_draft_status(client):
    s = _open(client, "cbn-fraud-forgeries", "2026-09")
    _patch(client, s["draft"]["id"], answers={"nil_return": True})
    client.post(f"/api/returns/drafts/{s['draft']['id']}/generate")
    cal = client.get("/api/returns/catalog").json()["calendar"]
    item = next((i for i in cal if i["return_id"] == "cbn-fraud-forgeries" and i["period"] == "2026-09"), None)
    if item:  # present only while that deadline is still ahead
        assert item["status"] == "generated" and item["draft_id"] == s["draft"]["id"]


def test_drafts_are_private_to_the_workspace(client, db):
    from models.database import User
    s = _open(client, "cbn-fraud-forgeries", "2026-09")
    db.add(User(id="other", email="other@example.invalid", hashed_password="x", role="analyst"))
    db.commit()
    other = db.get(User, "other")
    app = client.app
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(f"/api/returns/drafts/{s['draft']['id']}").status_code == 404
