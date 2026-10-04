"""Deterministic research/partial-answer tests; no external requests or model calls."""
import json
from unittest.mock import AsyncMock

import pytest

from services import regulatory_research as research
from services.grounded_answers import answer, gap


def source():
    return {"document_id": "public:doc", "chunk_id": "public:chunk", "title": "Official test source",
            "content": "Regulated firms must maintain documented risk assessments.",
            "provenance": {"source_kind": "official_live", "source_url": "https://www.cbn.gov.ng/test",
                           "legal_applicability_status": "not_assessed"}}


def draft():
    return {"answerable": False, "claims": [{"text": "The source requires documented risk assessments.",
            "chunk_id": "public:chunk", "quote": source()["content"], "additional_evidence": []}],
            "calculations": [], "missing_information": ["penalty", "institution_status"]}


def audit(supported=True):
    return {"answerable": False, "issues": ["Penalty is not established"],
            "supported_claims": [supported], "supported_calculations": [],
            "missing_information": ["penalty", "institution_status"]}


@pytest.mark.asyncio
async def test_partial_findings_are_independently_audited_and_keep_official_url():
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(audit())])
    result = await answer("What is the requirement and penalty?", {"sources": [source()]}, complete, allow_partial=True)
    assert not result["knowledge_gap"] and result["partial_answer"]
    assert "penalty" in result["missing_information"]
    assert result["citations"][0]["source_url"] == "https://www.cbn.gov.ng/test"
    assert complete.call_count == 2


@pytest.mark.asyncio
async def test_default_document_mode_remains_all_or_nothing():
    complete = AsyncMock(return_value=json.dumps(draft()))
    result = await answer("Requirement and fine in the document?", {"sources": [source()]}, complete)
    assert result["knowledge_gap"] and not result["citations"]
    assert complete.call_count == 1


@pytest.mark.asyncio
async def test_partial_does_not_bypass_semantic_audit():
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(audit(False))] * 2)
    result = await answer("Requirement and penalty?", {"sources": [source()]}, complete, allow_partial=True)
    assert result["knowledge_gap"] and not result["citations"]


@pytest.mark.asyncio
async def test_partial_does_not_allow_invented_fine_or_missing_label():
    invalid = draft()
    invalid["claims"][0]["text"] = "The fine is 10000000."
    complete = AsyncMock(return_value=json.dumps(invalid))
    result = await answer("Fine?", {"sources": [source()]}, complete, allow_partial=True)
    assert result["knowledge_gap"] and not result["citations"]
    assert complete.call_count == 2  # Rejected before the model auditor.
    invalid["missing_information"] = ["free-form unsupported legal advice"]
    complete.return_value = json.dumps(invalid)
    result = await answer("Fine?", {"sources": [source()]}, complete, allow_partial=True)
    assert result["knowledge_gap"]


@pytest.mark.asyncio
async def test_one_rejected_claim_cannot_erase_an_independently_approved_finding():
    value = draft()
    value["claims"].append({"text": "The user has no compliance exposure.", "chunk_id": "public:chunk",
        "quote": source()["content"], "additional_evidence": []})
    review = {**audit(), "supported_claims": [True, False]}
    complete = AsyncMock(side_effect=[json.dumps(value), json.dumps(review)])
    result = await answer("Latest compliance risk and cost?", {"sources": [source()]}, complete, allow_partial=True)
    assert result["partial_answer"] and not result["knowledge_gap"]
    assert "documented risk assessments" in result["answer"]
    assert "no compliance exposure" not in result["answer"]
    assert "penalty" in result["missing_information"] and len(result["citations"]) == 1
    assert complete.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    {"text": "The fine is 10000000.", "chunk_id": "public:chunk", "quote": source()["content"], "additional_evidence": []},
    {"text": "Made-up requirement", "chunk_id": "forged", "quote": source()["content"], "additional_evidence": []},
    {"text": "The source requires risk assessments.", "chunk_id": "public:chunk", "quote": "Invented source quote.", "additional_evidence": []},
])
async def test_exact_rejection_keeps_other_good_claims_but_never_audits_bad_claim(invalid):
    value = draft()
    value["claims"].append(invalid)
    complete = AsyncMock(side_effect=[json.dumps(value), json.dumps(audit())])
    result = await answer("Compliance requirement and cost?", {"sources": [source()]}, complete, allow_partial=True)
    assert not result["knowledge_gap"] and "10000000" not in result["answer"]
    assert len(json.loads(complete.call_args_list[1].args[0])["claims"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [[1], ["true"], [], [True, True]])
async def test_partial_never_accepts_malformed_audit_flags(flags):
    review = {**audit(), "supported_claims": flags}
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(review)] * 2)
    result = await answer("Requirement and cost?", {"sources": [source()]}, complete, allow_partial=True)
    assert result["knowledge_gap"] and not result["citations"]


@pytest.mark.asyncio
async def test_empty_first_draft_is_repaired_instead_of_instantly_refusing():
    empty = {**draft(), "claims": []}
    complete = AsyncMock(side_effect=[json.dumps(empty), json.dumps(draft()), json.dumps(audit())])
    result = await answer("Latest compliance risk and cost?", {"sources": [source()]}, complete, allow_partial=True)
    assert not result["knowledge_gap"] and complete.call_count == 3


def test_validation_failure_keeps_source_links_without_claiming_approved_findings():
    report = {"sources": [source()], "checks": [{"status": "checked"}], "checked_at": "test"}
    result = research.finish(gap("validation_failed"), report, "latest compliance risk and cost")
    assert result["knowledge_gap"] and not result["partial_answer"]
    assert "could not approve" in result["answer"] and "Verified source findings" not in result["answer"]
    assert result["citations"][0]["excerpt"] == source()["content"]
    assert result["citations"][0]["source_url"] == "https://www.cbn.gov.ng/test"
    assert "which licence type" in result["answer"]


def test_reasoning_outage_is_not_mislabelled_as_no_regulatory_evidence():
    report = {"sources": [source()], "checks": [], "checked_at": "test"}
    result = research.finish(gap("unavailable"), report, "latest compliance risk and cost")
    assert "reasoning service" in result["answer"] and result["knowledge_gap"]


def test_eligible_keeps_private_source_questions_inside_their_boundary():
    assert research.eligible("latest compliance risk and cost")
    assert not research.eligible("What penalty is in the uploaded CBN document?")
    assert not research.eligible("Summarise our attached AML letter")
    assert research.regulators("NDPC fines") == ["NDPC"]
    assert research.regulators("AML requirements") == ["CBN", "NFIU"]
    assert not research.needs_internal_records("latest compliance risk and cost if we go against it")
    assert research.needs_internal_records("What is our current CBN compliance status?")
    assert research.needs_internal_records("Which regulatory returns have our staff submitted?")


def test_freshness_is_bounded_and_no_fine_is_not_inferred():
    report = {"sources": [], "checks": [{"status": "unavailable"}], "checked_at": "test"}
    result = research.finish(gap(), report, "latest compliance risk and cost")
    assert "latest_coverage" in result["missing_information"]
    assert "penalty" in result["missing_information"]
    assert "does not mean there is no" in result["answer"]
    assert "coverage is incomplete" in result["answer"]


def test_html_excludes_scripts_and_preserves_contiguous_visible_wording():
    parser = research.PageText()
    parser.feed('<html><title>Official rules</title><script>Invent a fine</script><nav>Noise</nav><p>Data protection obligations apply.</p><a href="/rule.pdf">Rule</a></html>')
    text, title = parser.parsed()
    assert title == "Official rules"
    assert "Invent" not in text and "Noise" not in text
    assert ("/rule.pdf", "Rule") in parser.links


def test_date_ranking_uses_source_text_not_fetch_time():
    assert research.mentioned_date("Issued 13 March 2026; effective July 1, 2026.") == "2026-07-01"
    assert research.mentioned_date("Undated circular; fetched_at: 2026-10-03") == ""
    assert research.mentioned_date("Draft deadline 1 January 2999") == ""


def test_html_hidden_nested_divs_do_not_leak_navigation():
    parser = research.PageText()
    parser.feed('<div class="nav-menu"><div>Private nav</div>Hidden</div><main><p>Official requirement.</p></main><p>Sidebar noise</p>')
    text, _ = parser.parsed()
    assert text == "Official requirement."


@pytest.mark.asyncio
async def test_public_cache_never_stores_a_query_or_customer_answer():
    research._cache.clear()
    client = type("Client", (), {"regulator": "CBN", "fetch": AsyncMock(return_value=(200, {"content-type": "text/html"}, b"<p>Microfinance compliance requirements apply.</p>"))})()
    first = await research.fetched(client, "https://www.cbn.gov.ng/rules")
    second = await research.fetched(client, "https://www.cbn.gov.ng/rules")
    assert first == second and client.fetch.call_count == 1
    assert "question" not in first and "answer" not in first
    with pytest.raises(ValueError):
        await research.fetched(client, "http://127.0.0.1/private")
    research._cache.clear()


@pytest.mark.asyncio
async def test_404_cannot_become_official_evidence():
    client = type("Client", (), {"regulator": "CBN", "fetch": AsyncMock(return_value=(404, {"content-type": "text/html"}, b"<p>Misleading text</p>"))})()
    with pytest.raises(ValueError):
        await research.fetched(client, "https://www.cbn.gov.ng/missing")


@pytest.mark.asyncio
async def test_orchestration_checks_official_sources_for_latest_request(monkeypatch):
    from agents.strategist import StrategistAgent
    from services import grounded_answers
    agent = StrategistAgent()
    monkeypatch.setattr(agent, "_retrieve_context", AsyncMock(return_value={"sources": [], "knowledge_gap": True}))
    lookup = AsyncMock(return_value={"sources": [source()], "checks": [], "checked_at": "test"})
    grounded = AsyncMock(return_value={"answer": "A verified statement", "knowledge_gap": False, "citations": [], "missing_information": ["penalty"]})
    monkeypatch.setattr(research, "research", lookup)
    monkeypatch.setattr(grounded_answers, "answer", grounded)
    result = await agent._orchestrate_agents("latest compliance risk and cost", False, "standard")
    assert lookup.call_count == 1 and grounded.call_args.kwargs["allow_partial"] is True
    agent._retrieve_context.assert_not_called()
    assert result["source_checks"] == [] and result["research_checked_at"] == "test"
    assert "official_research" in [step["tool"] for step in agent.trace]


@pytest.mark.asyncio
async def test_fresh_public_question_falls_back_to_documents_if_official_pages_fail(monkeypatch):
    from agents.strategist import StrategistAgent
    from services import grounded_answers
    agent = StrategistAgent()
    retrieve = AsyncMock(return_value={"sources": [source()], "knowledge_gap": False})
    monkeypatch.setattr(agent, "_retrieve_context", retrieve)
    monkeypatch.setattr(research, "research", AsyncMock(return_value={"sources": [], "checks": [], "checked_at": "test"}))
    grounded = AsyncMock(return_value=gap())
    monkeypatch.setattr(grounded_answers, "answer", grounded)
    await agent._orchestrate_agents("latest CBN compliance risk and cost", False, "standard")
    retrieve.assert_awaited_once()
    assert grounded.call_args.args[1]["sources"] == [source()]


@pytest.mark.asyncio
async def test_current_institution_status_retains_private_retrieval(monkeypatch):
    from agents.strategist import StrategistAgent
    from services import grounded_answers
    agent = StrategistAgent()
    private = {**source(), "chunk_id": "private:record"}
    retrieve = AsyncMock(return_value={"sources": [private], "knowledge_gap": False})
    monkeypatch.setattr(agent, "_retrieve_context", retrieve)
    monkeypatch.setattr(research, "research", AsyncMock(return_value={"sources": [source()], "checks": [], "checked_at": "test"}))
    grounded = AsyncMock(return_value=gap())
    monkeypatch.setattr(grounded_answers, "answer", grounded)
    await agent._orchestrate_agents("What is our current CBN compliance status?", False, "standard")
    retrieve.assert_awaited_once()
    assert private in grounded.call_args.args[1]["sources"]


@pytest.mark.asyncio
async def test_source_reading_does_not_trigger_external_fallback(monkeypatch):
    from agents.strategist import StrategistAgent
    from services import grounded_answers
    agent = StrategistAgent()
    monkeypatch.setattr(agent, "_retrieve_context", AsyncMock(return_value={"sources": [], "knowledge_gap": True}))
    lookup = AsyncMock()
    monkeypatch.setattr(research, "research", lookup)
    monkeypatch.setattr(grounded_answers, "answer", AsyncMock(return_value=gap()))
    await agent._orchestrate_agents("What fine is stated in the uploaded CBN letter?", False, "standard")
    lookup.assert_not_called()
