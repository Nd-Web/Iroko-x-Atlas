"""Compliance verdicts: silence is never GO, and every verdict stands on a rule quoted from a retrieved document."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.watchdog import WatchdogAgent
from routes.compliance_api import UNVERIFIED_FLAG, derive_verdict

RULE = ("In view of the above, all OFIs are required to immediately divest from all managed funds "
        "or products of uninsured entities and desist from such investments in future.")
PASSAGE = {"document_id": "doc-1", "title": "Prohibition of Placement in Funds Managed by Uninsured Entities",
           "excerpt": "The CBN has observed that OFIs hold assets with uninsured entities. " + RULE
           + " Any existing placement must be reported to the CBN within two weeks of this circular."}
EVIDENCE = {"quote": RULE, "document_id": "doc-1", "title": PASSAGE["title"]}


def test_nothing_found_is_unverified_never_go():
    result = derive_verdict({"assessment": "not_covered", "basis": "", "alerts": [], "evidence": None,
                             "missing_source": "the Nigeria Data Protection Act 2023"})
    assert result["verdict"] == "MONITOR"
    assert result["flags"] == [UNVERIFIED_FLAG]
    assert result["confidence"] < 0.5
    assert "could not verify" in result["reasoning"]
    assert "Nigeria Data Protection Act 2023, which is not in the library" in result["reasoning"]


def test_compliant_claim_without_quoted_rule_is_not_go():
    result = derive_verdict({"assessment": "compliant", "basis": "Generally allowed.", "alerts": [], "evidence": None})
    assert result["verdict"] == "MONITOR"
    assert result["flags"] == [UNVERIFIED_FLAG]


def test_breach_with_evidence_is_no_go_and_cites_the_rule():
    result = derive_verdict({
        "assessment": "breach", "basis": "CBN letter OFI/DOA/CON/OFI/001/304", "evidence": EVIDENCE,
        "alerts": [{"severity": "critical for a breach", "title": "Placement with an uninsured fund",
                    "summary": "The circular requires OFIs to divest.", "metadata": {"regulation": "OFI/DOA/CON/OFI/001/304"}}],
    })
    assert result["verdict"] == "NO-GO"
    assert result["flags"] == ["Placement with an uninsured fund"]
    assert result["regulation"] == "OFI/DOA/CON/OFI/001/304"
    assert result["evidence"] == RULE
    assert result["source"] == PASSAGE["title"]


def test_breach_without_alert_list_still_blocks():
    result = derive_verdict({"assessment": "breach", "basis": "OFIs must divest from uninsured funds.",
                             "evidence": EVIDENCE, "alerts": []})
    assert result["verdict"] == "NO-GO"
    assert result["reasoning"] == "OFIs must divest from uninsured funds."


def test_safeguards_stay_monitor_even_when_the_alert_says_critical():
    result = derive_verdict({"assessment": "needs_safeguards", "basis": "Consent clause required.", "evidence": EVIDENCE,
                             "alerts": [{"severity": "critical", "title": "Consent clause missing", "summary": "Add it."}]})
    assert result["verdict"] == "MONITOR"
    assert result["flags"] == ["Consent clause missing"]


def test_compliant_with_quoted_rule_is_go():
    result = derive_verdict({"assessment": "compliant", "basis": "AML/CFT returns are due by the 14th.",
                             "evidence": EVIDENCE, "alerts": []})
    assert result["verdict"] == "GO"
    assert result["regulation"] == "AML/CFT returns are due by the 14th."
    assert result["evidence"] == RULE


def test_rule_quote_is_checked_sentence_by_sentence():
    joined = RULE + " ... Any existing placement must be reported to the CBN within two weeks of this circular."
    evidence = WatchdogAgent._verified_rule(joined, [PASSAGE])
    assert evidence["document_id"] == "doc-1"
    assert evidence["quote"].startswith("In view of the above")
    assert "within two weeks" in evidence["quote"]


@pytest.mark.parametrize("quote", [
    "The Management of an OFI shall:",                                      # a fragment states no rule
    "All OFIs must obtain written customer consent before sharing any BVN data with partners.",  # not in the text
    "",
    None,
])
def test_unsupported_rule_quotes_are_rejected(quote):
    assert WatchdogAgent._verified_rule(quote, [PASSAGE]) is None


@pytest.fixture
def engine_with(monkeypatch):
    import agents.watchdog as watchdog

    agent = WatchdogAgent()
    calls = []

    async def search(self, query, doc_type=None, top_k=8):
        return [PASSAGE]

    def reply(payload):
        async def complete(prompt, **kwargs):
            calls.append(prompt)
            return payload if isinstance(payload, str) else json.dumps(payload)
        monkeypatch.setattr(watchdog, "llm_complete", complete)

    monkeypatch.setattr(WatchdogAgent, "_search_documents", search)
    return agent, reply, calls


async def test_assessment_keeps_a_verified_breach(engine_with):
    agent, reply, _ = engine_with
    reply({"assessment": "breach", "rule_quote": RULE, "basis": "CBN letter", "alerts": [
        {"severity": "critical", "title": "Uninsured placement", "summary": "Must divest."}]})
    result = await agent.assess_proposed_action("Invest deposits in an uninsured fund")
    assert result["assessment"] == "breach"
    assert result["evidence"]["quote"] == RULE


async def test_assessment_downgrades_a_rule_the_documents_do_not_state(engine_with):
    agent, reply, _ = engine_with
    reply({"assessment": "breach", "rule_quote": "Customer data may never be shared with marketing partners without consent.",
           "basis": "NDPA 2023 s25", "alerts": [{"severity": "critical", "title": "No consent", "summary": "x"}]})
    result = await agent.assess_proposed_action("Share BVN data with a marketing partner")
    assert result["assessment"] == "not_covered"
    assert result["unverified_rule"] is True
    assert result["alerts"] == []
    assert derive_verdict(result)["verdict"] == "MONITOR"


async def test_no_retrieved_documents_is_not_covered_without_a_model_call(engine_with, monkeypatch):
    agent, _, calls = engine_with

    async def nothing(self, query, doc_type=None, top_k=8):
        return []

    monkeypatch.setattr(WatchdogAgent, "_search_documents", nothing)
    result = await agent.assess_proposed_action("Run with a 12 percent liquidity ratio")
    assert result["assessment"] == "not_covered"
    assert calls == []


async def test_unreadable_model_output_is_an_error_not_a_verdict(engine_with):
    agent, reply, _ = engine_with
    reply("Sorry, I cannot help with that.")
    with pytest.raises(RuntimeError, match="unreadable"):
        await agent.assess_proposed_action("Anything")


@pytest.fixture
def api(monkeypatch):
    from ingestion.models import PipelineBase
    from models.database import Base, User, get_db
    from routes import compliance_api

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
                           execution_options={"schema_translate_map": {"ingestion": None}})
    Base.metadata.create_all(engine)
    PipelineBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(id="officer", email="officer@example.invalid", hashed_password="unused", role="analyst")
    db.add(user)
    db.commit()
    app = FastAPI()
    app.include_router(compliance_api.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[compliance_api._optional_jwt_user] = lambda: user
    assessments = {}

    async def assess(topic, sector="financial"):
        return assessments["next"]

    monkeypatch.setattr(compliance_api._watchdog, "assess_proposed_action", assess)
    with TestClient(app) as client:
        yield client, assessments
    db.close()
    engine.dispose()


def test_route_returns_the_quoted_rule_with_the_verdict(api):
    client, assessments = api
    assessments["next"] = {"assessment": "breach", "basis": "CBN letter", "evidence": EVIDENCE, "missing_source": "",
                           "alerts": [{"severity": "critical", "title": "Uninsured placement", "summary": "Must divest."}]}
    body = client.post("/api/v1/compliance/check", json={"text": "Invest deposits in an uninsured fund"}).json()
    assert body["verdict"] == "NO-GO"
    assert body["evidence"] == RULE
    assert body["source"] == PASSAGE["title"]


def test_route_no_longer_clears_what_it_cannot_check(api):
    client, assessments = api
    assessments["next"] = {"assessment": "not_covered", "basis": "", "evidence": None, "missing_source": "", "alerts": []}
    body = client.post("/api/v1/compliance/check", json={"text": "Run with a 12 percent liquidity ratio"}).json()
    assert body["verdict"] == "MONITOR"
    assert body["flags"] == [UNVERIFIED_FLAG]
    assert body["evidence"] is None
