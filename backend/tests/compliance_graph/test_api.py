"""The HTTP surface: flags, permissions as status codes, isolation, serialisation, export."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.compliance_graph import Control, Link
from models.database import AuditLog, get_db
from services.auth_utils import create_access_token
from tests.compliance_graph import factory as f
from tests.compliance_graph.test_workspace import extract, sync


@pytest.fixture
def client(db):
    from routes.compliance_graph import router

    app = FastAPI()
    app.include_router(router)

    def dependency():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as c:
        yield c


def auth(user_id, role):
    return {"Authorization": "Bearer " + create_access_token(user_id, role)}


@pytest.fixture
async def seeded(db):
    f.user(db, "iroko", role="superadmin", workspace="ws-lib")
    f.user(db, "ada", role="admin", workspace="ws-a")
    f.user(db, "ali", role="analyst", workspace="ws-a")
    f.user(db, "bola", role="admin", workspace="ws-b")
    f.document(db, "bvn", title="BVN Enrollment for OFIs Customers", pages=[f.BVN_LETTER], workspace="ws-lib",
               shared=True, regulator="CBN", reference="OFI/DIR/CIR/GEN/17/139", uploaded_by="iroko")
    f.document(db, "pol", title="AML/CFT Policy", pages=[f.AML_POLICY], workspace="ws-a", role="policy",
               uploaded_by="ada")
    await extract(db, "bvn")
    await extract(db, "pol", f.FakeModel(role="policy"))
    await sync(db, "ws-a")


ADA, ALI, BOLA, IROKO = auth("ada", "admin"), auth("ali", "analyst"), auth("bola", "admin"), auth("iroko", "superadmin")


async def test_disabled_flag_returns_503(client, monkeypatch, seeded):
    monkeypatch.setenv("COMPLIANCE_GRAPH_ENABLED", "false")
    assert client.get("/api/compliance-graph/overview", headers=ADA).status_code == 503


async def test_reads_serialise_for_a_member(client, seeded):
    for path in ["/overview", "/requirements", "/requirements?coverage=control_suggested&page_size=5", "/controls",
                 "/review-queue", "/impacts", "/due?days=60", "/search?q=BVN", "/profile", "/categories", "/people",
                 "/admin/runs"]:
        response = client.get("/api/compliance-graph" + path, headers=ADA)
        assert response.status_code == 200, (path, response.text)
    requirements = client.get("/api/compliance-graph/requirements", headers=ADA).json()
    assert requirements["total"] >= 3 and requirements["items"][0]["document"]["title"]
    lineage = requirements["items"][0]["lineage_id"]
    detail = client.get(f"/api/compliance-graph/requirements/{lineage}", headers=ADA)
    assert detail.status_code == 200 and detail.json()["versions"]
    hood = client.get(f"/api/compliance-graph/neighbourhood?type=requirement&id={lineage}&depth=2", headers=ADA)
    assert hood.status_code == 200 and hood.json()["nodes"]


async def test_permissions_are_status_codes(client, db, seeded):
    assert client.put("/api/compliance-graph/profile", json={"category_codes": ["state"]}, headers=ALI).status_code == 403
    assert client.put("/api/compliance-graph/profile", json={"category_codes": ["state"]}, headers=ADA).status_code == 200
    assert client.put("/api/compliance-graph/profile", json={"category_codes": ["bdc"]}, headers=ADA).status_code == 422
    link = db.query(Link).filter(Link.workspace_id == "ws-a", Link.relation == "addresses").first()
    body = {"kind": "link", "id": link.id, "decision": "confirm"}
    assert client.post("/api/compliance-graph/review", json=body, headers=ALI).status_code == 403
    assert client.post("/api/compliance-graph/review", json=body, headers=BOLA).status_code == 404
    confirmed = client.post("/api/compliance-graph/review", json=body, headers=ADA)
    assert confirmed.status_code == 200 and confirmed.json()["status"]["review_status"] == "confirmed"
    assert client.get(f"/api/compliance-graph/links/{link.id}", headers=BOLA).status_code == 404
    reject = {"kind": "link", "id": link.id, "decision": "reject"}
    assert client.post("/api/compliance-graph/review", json=reject, headers=ADA).status_code == 422
    applies = db.query(Link).filter(Link.relation == "applies_to").first()
    library = {"kind": "link", "id": applies.id, "decision": "confirm"}
    assert client.post("/api/compliance-graph/review", json=library, headers=ADA).status_code == 403
    assert client.post("/api/compliance-graph/review", json=library, headers=IROKO).status_code == 200
    assert client.post("/api/compliance-graph/admin/backfill", json={}, headers=ALI).status_code == 403


async def test_controls_and_status_through_the_api(client, db, seeded):
    created = client.post("/api/compliance-graph/controls", headers=ALI,
                          json={"name": "Quarterly KYC file review", "frequency": "quarterly", "owner_user_id": "ada"})
    assert created.status_code == 200, created.text
    control = created.json()["control"]
    assert control["review"]["review_status"] == "proposed"
    assert client.patch(f"/api/compliance-graph/controls/{control['id']}", headers=ADA,
                        json={"owner_user_id": "bola"}).status_code == 422
    assert client.get(f"/api/compliance-graph/controls/{control['id']}", headers=BOLA).status_code == 404
    lineage = client.get("/api/compliance-graph/requirements", headers=ADA).json()["items"][0]["lineage_id"]
    status = client.put(f"/api/compliance-graph/requirements/{lineage}/status", headers=ADA,
                        json={"owner_user_id": "ali", "next_due_date": "2026-12-31", "recurrence": "quarterly"})
    assert status.status_code == 200, status.text
    assert status.json()["requirement"]["owner"]["name"] == "Ali"
    assert client.put(f"/api/compliance-graph/requirements/{lineage}/status", headers=ALI,
                      json={"owner_team": "Compliance"}).status_code == 403


async def test_export_download_is_audited(client, db, seeded):
    response = client.get("/api/compliance-graph/export.xlsx", headers=ADA)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in response.headers["content-disposition"]
    assert response.content[:2] == b"PK"
    assert db.query(AuditLog).filter(AuditLog.action == "compliance_graph_export").count() == 1


async def test_other_workspaces_controls_are_invisible(client, db, seeded):
    control = db.query(Control).filter(Control.workspace_id == "ws-a").first()
    assert control.id not in client.get("/api/compliance-graph/controls", headers=BOLA).text
    assert "AML/CFT Policy" not in client.get("/api/compliance-graph/search?q=AML", headers=BOLA).text
    assert "AML/CFT Policy" in client.get("/api/compliance-graph/search?q=AML", headers=ADA).text
