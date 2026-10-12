"""Definitions remain evidence-backed but do not inherit unrelated legal tasks."""

import json
from unittest.mock import AsyncMock

import pytest

from agents.strategist import StrategistAgent
from services.grounded_answers import answer, concept_explanation

TEXT = "Access permits licensed exchange operators to purchase foreign currency through authorised dealer banks."
SOURCE = {"document_id": "public:definition", "chunk_id": "public:definition-chunk",
          "title": "Exchange-access framework fixture", "content": TEXT,
          "provenance": {"source_url": "https://www.cbn.gov.ng/definition-fixture", "source_kind": "official_live"}}
CLAIM = {"text": "In the framework, foreign-exchange access means licensed exchange operators can obtain foreign currency through authorised dealer banks.",
         "chunk_id": SOURCE["chunk_id"], "quote": TEXT, "additional_evidence": []}


@pytest.mark.parametrize("question,expected", [
    ("what is Bureau de Change foreign-exchange access", True),
    ("Explain customer due diligence in plain language", True),
    ("What does KYC mean?", True),
    ("Define agent banking", True),
    ("What is the latest BDC access rule?", False),
    ("What is BDC access and how much is the fine?", False),
    ("Explain BDC access and whether our firm is compliant", False),
    ("What is the current licensing deadline?", False),
])
def test_explanation_hint_never_relaxes_current_rule_or_penalty_requests(question, expected):
    assert concept_explanation(question) is expected


def draft(missing=None, claim=None):
    missing = missing or []
    return {"answerable": not missing, "claims": [claim or CLAIM], "calculations": [],
            "direct_answer": "", "followup_questions": [], "missing_information": missing}


def audit(missing=None, supported=True):
    missing = missing or []
    return {"answerable": supported and not missing, "supported_claims": [supported],
            "supported_calculations": [], "direct_answer_supported": True,
            "irrelevant_draft_gaps": [], "issues": [], "missing_information": missing}


async def test_supported_plain_definition_is_complete_without_licence_or_document_clarification():
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(audit())])
    result = await answer("What is foreign-exchange access?", {"sources": [SOURCE]}, complete, answer_mode="helpful")
    assert result["answer_status"] == "answered"
    assert "obtain foreign currency" in result["answer"]
    assert "Which document" not in result["answer"] and "Still to establish" not in result["answer"]
    assert result["citations"][0]["source_url"] == SOURCE["provenance"]["source_url"]
    assert complete.await_count == 2
    for call in complete.call_args_list:
        assert json.loads(call.args[0])["answer_task"] == "concept_explanation"
        assert "exact supporting quote" in call.kwargs["system_prompt"]


async def test_definition_still_rejects_a_semantically_unsupported_explanation():
    bad = {**CLAIM, "text": "Access means all operators can purchase unlimited foreign currency without checks."}
    complete = AsyncMock(side_effect=[json.dumps(draft(claim=bad)), json.dumps(audit(supported=False))] * 2)
    result = await answer("What is foreign-exchange access?", {"sources": [SOURCE]}, complete, answer_mode="helpful")
    assert result["knowledge_gap"]
    assert "unlimited" not in result["answer"]
    assert result["citations"] == []


async def test_definition_plus_fine_keeps_definition_but_does_not_invent_fine():
    complete = AsyncMock(side_effect=[json.dumps(draft(["penalty"])), json.dumps(audit(["penalty"]))])
    result = await answer("What is foreign-exchange access and what fine applies?", {"sources": [SOURCE]}, complete, answer_mode="helpful")
    assert result["answer_status"] == "partial"
    assert result["missing_information"] == ["penalty"]
    assert "obtain foreign currency" in result["answer"]
    assert "monetary penalty has not been established" in result["answer"]
    assert json.loads(complete.call_args_list[0].args[0])["answer_task"] == "evidence_question"


async def test_actual_bdc_followup_uses_current_question_and_rechecks_prior_source(monkeypatch):
    query = "what is Bureau de Change foreign-exchange access"
    history = [{"question": "Tell me everything about the latest Bureau de Change foreign-exchange access framework",
                "intent": "regulatory_compliance",
                "answer_summary": "UNVERIFIED HISTORICAL CLAIM: every operator has automatic access.",
                "citations": [{"document_id": SOURCE["document_id"], "document_title": "CBN Bureau de Change foreign-exchange access framework",
                               "source_url": SOURCE["provenance"]["source_url"]}]}]
    agent = StrategistAgent()
    agent.set_history(history)
    retrieve = AsyncMock(return_value={"sources": [], "knowledge_gap": True, "retrieval_status": "empty"})
    lookup = AsyncMock(return_value={"sources": [SOURCE], "checks": [], "checked_at": "test"})
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(audit())])
    monkeypatch.setattr("services.grounded_answers.retrieve", retrieve)
    monkeypatch.setattr("services.regulatory_research.research", lookup)
    monkeypatch.setattr("agents.strategist.llm_complete", complete)
    result = json.loads(await agent.investigate(query))
    assert result["answer_status"] == "answered"
    assert result["intent"] == "follow_up"
    assert result["missing_information"] == []
    assert "UNVERIFIED HISTORICAL CLAIM" not in result["answer"]
    assert "Which document" not in result["answer"]
    assert lookup.call_args.kwargs["source_references"][0]["source_url"] == SOURCE["provenance"]["source_url"]
    assert retrieve.await_count == 1
    for call in complete.call_args_list:
        payload = json.loads(call.args[0])
        assert payload["question"] == query
        assert payload["answer_task"] == "concept_explanation"
        assert "UNVERIFIED HISTORICAL CLAIM" not in json.dumps(payload["evidence"])


async def test_a_missing_source_never_uses_previous_answer_as_evidence(monkeypatch):
    agent = StrategistAgent()
    agent.set_history([{"question": "Explain Bureau de Change foreign-exchange access",
                        "answer_summary": "Every operator can buy currency without checks.",
                        "citations": [{"document_title": "Bureau de Change foreign-exchange access framework",
                                       "document_id": "public:unavailable"}]}])
    monkeypatch.setattr("services.grounded_answers.retrieve", AsyncMock(return_value={"sources": [], "knowledge_gap": True}))
    monkeypatch.setattr("services.regulatory_research.research", AsyncMock(return_value={"sources": [], "checks": [], "checked_at": "test"}))
    model = AsyncMock(side_effect=AssertionError("No evidence means no factual model drafting"))
    monkeypatch.setattr("agents.strategist.llm_complete", model)
    result = json.loads(await agent.investigate("what is Bureau de Change foreign-exchange access"))
    assert result["knowledge_gap"]
    assert "without checks" not in result["answer"]
    model.assert_not_awaited()
