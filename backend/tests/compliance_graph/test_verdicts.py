"""Verdict flags from the graph: never GO, never softer."""

from datetime import date, timedelta

from models.compliance_graph import GraphDocument, Link
from services.compliance_graph import review
from services.compliance_graph.verdicts import apply_rule_status
from services.compliance_graph.visibility import for_user
from tests.compliance_graph import factory as f
from tests.compliance_graph.test_workspace import extract

REVOKING = """CENTRAL BANK OF NIGERIA

Ref: OFI/DIR/CIR/GEN/20/900

May 4, 2020

# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)

The CBN hereby revokes circular OFI/DIR/CIR/GEN/17/139 on BVN enrollment.
"""


async def test_revoked_amended_and_future_rules_are_flagged(db):
    iroko = f.user(db, "iroko", role="superadmin", workspace="ws-lib")
    ada = f.user(db, "ada", role="admin", workspace="ws-a")
    f.document(db, "bvn", title="BVN Enrollment", pages=[f.BVN_LETTER], workspace="ws-lib", shared=True,
               regulator="CBN", reference="OFI/DIR/CIR/GEN/17/139", uploaded_by="iroko")
    await extract(db, "bvn")
    assessment = {"evidence": {"document_id": "bvn", "quote": "All OFIs shall ensure ..."}}
    go = {"verdict": "GO", "confidence": 0.85, "flags": [], "reasoning": "x", "regulation": "y"}
    assert apply_rule_status(db, ada, assessment, go)["verdict"] == "GO"

    f.document(db, "rev", title="Revocation of the BVN circular", pages=[REVOKING], workspace="ws-lib", shared=True,
               regulator="CBN", reference="OFI/DIR/CIR/GEN/20/900", uploaded_by="iroko")
    await extract(db, "rev")
    revokes = db.query(Link).filter(Link.relation == "revokes").one()
    assert revokes.basis == "stated"
    # Stated is not enough to change a verdict; a confirmation is.
    assert apply_rule_status(db, ada, assessment, go)["verdict"] == "GO"
    review.review_link(db, for_user(db, iroko), revokes.id, "confirm")
    flagged = apply_rule_status(db, ada, assessment, go)
    assert flagged["verdict"] == "MONITOR" and flagged["confidence"] <= 0.5
    assert any("revoked or replaced" in flag for flag in flagged["flags"])
    no_go = {"verdict": "NO-GO", "confidence": 0.9, "flags": [], "reasoning": "x", "regulation": "y"}
    assert apply_rule_status(db, ada, assessment, no_go)["verdict"] == "NO-GO"

    gd = db.get(GraphDocument, "bvn")
    gd.effective_date, gd.effective_basis = date.today() + timedelta(days=40), "confirmed"
    db.commit()
    assert any("not yet in force" in flag for flag in apply_rule_status(db, ada, assessment, go)["flags"])


async def test_disabled_graph_changes_nothing(db, monkeypatch):
    monkeypatch.setenv("COMPLIANCE_GRAPH_ENABLED", "false")
    ada = f.user(db, "ada", role="admin", workspace="ws-a")
    result = {"verdict": "GO", "confidence": 0.85, "flags": []}
    assert apply_rule_status(db, ada, {"evidence": {"document_id": "x"}}, result) is result
