import json
from unittest.mock import AsyncMock

import pytest

from services.grounded_answers import answer, audit_flags, gap, render, validated_candidates


def source(content="STRs must be submitted to NFIU within 24 hours."):
    return {
        "chunk_id": "real_chunk",
        "document_id": "real_document",
        "title": "Extracted circular",
        "content": content,
        "provenance": {"historical_document": True},
    }


def draft(text="STRs go to NFIU within 24 hours.", quote=None):
    return {
        "answerable": True,
        "claims": [{"text": text, "chunk_id": "real_chunk", "quote": quote or source()["content"]}],
        "calculations": [],
    }


def audit():
    return {
        "answerable": True,
        "issues": [],
        "supported_claims": [True],
        "supported_calculations": [],
    }


def test_exact_quote_and_server_owned_citation():
    sources = {"real_chunk": source()}
    claims, calculations = validated_candidates(draft(), sources, "STR deadline?")
    result = render(claims, calculations, sources)
    assert result["citations"][0]["document_id"] == "real_document"
    assert result["citations"][0]["chunk_id"] == "real_chunk"
    assert "[1]" in result["answer"]
    assert "current legal applicability has not been verified" in result["answer"]


@pytest.mark.parametrize(
    "item",
    [
        {
            "text": "A claim",
            "chunk_id": "forged",
            "quote": "STRs must be submitted to NFIU within 24 hours.",
        },
        {
            "text": "A claim",
            "chunk_id": "real_chunk",
            "quote": "An invented quote that does not exist.",
        },
        {
            "text": "There is a 10000000 fine.",
            "chunk_id": "real_chunk",
            "quote": "STRs must be submitted to NFIU within 24 hours.",
        },
    ],
)
def test_rejects_forged_source_quote_or_numeric_claim(item):
    value = {"answerable": True, "claims": [item], "calculations": []}
    assert validated_candidates(value, {"real_chunk": source()}, "test") == ([], [])


def test_html_table_quote_is_matched_without_changing_words():
    row = source("<td>Currency Transaction Reports</td><td>NFIU</td><td>Within 7 days</td>")
    value = draft(
        "CTRs go to NFIU within 7 days.", "Currency Transaction Reports NFIU Within 7 days"
    )
    assert len(validated_candidates(value, {"real_chunk": row}, "CTR?")[0]) == 1


def test_deterministic_arithmetic_requires_source_operand_and_requested_operation():
    row = source("Each branch acquires 64 new customers per month.")
    value = {
        "answerable": True,
        "claims": [],
        "calculations": [
            {
                "left": "64",
                "right": "12",
                "operation": "multiply",
                "chunk_id": "real_chunk",
                "quote": row["content"],
            }
        ],
    }
    _, calculations = validated_candidates(value, {"real_chunk": row}, "Calculate monthly times 12")
    assert calculations[0]["result"] == "64 × 12 = 768"
    value["calculations"][0]["right"] = "500000"
    assert validated_candidates(value, {"real_chunk": row}, "Calculate monthly times 12")[1] == []


@pytest.mark.asyncio
async def test_semantic_audit_blocks_claim_despite_valid_coordinates():
    rejected = {
        "answerable": False,
        "issues": ["Missing a requested fact"],
        "supported_claims": [],
        "supported_calculations": [],
    }
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(rejected)] * 2)
    result = await answer(
        "STR deadline?", {"sources": [source()], "knowledge_gap": False}, complete
    )
    assert result["knowledge_gap"] is True
    assert result["citations"] == []
    assert complete.call_count == 4  # At most one repair; no unchecked partial prose.


def test_workbook_presentation_escaping_preserves_contiguous_words():
    row = source('NB:\t"NEW CUSTOMERS" means customers whose BVN was registered by this MFB.')
    value = draft(
        "The MFB must have registered the BVN.",
        r"NB:\"NEW CUSTOMERS\" means customers whose BVN was registered by this MFB.",
    )
    assert len(validated_candidates(value, {"real_chunk": row}, "criterion?")[0]) == 1
    value["claims"][0]["quote"] = "NEW CUSTOMERS means customers ... registered by this MFB."
    assert validated_candidates(value, {"real_chunk": row}, "criterion?") == ([], [])


def test_comparisons_require_explicit_verified_additional_sources():
    first = source("In 2017, FTRs went to CBN and NFIU within 7 days.")
    second = {
        **source("In 2019, FTRs went to CBN within 24 hours."),
        "chunk_id": "second",
        "document_id": "second_doc",
    }
    sources = {"real_chunk": first, "second": second}
    value = draft("The 2017 and 2019 tables differ: 7 days versus 24 hours.", first["content"])
    assert validated_candidates(value, sources, "compare") == ([], [])
    value["claims"][0]["additional_evidence"] = [{"chunk_id": "second", "quote": second["content"]}]
    claims, calculations = validated_candidates(value, sources, "compare")
    result = render(claims, calculations, sources)
    assert len(result["citations"]) == 2
    assert "[1] [2]" in result["answer"]
    value["claims"][0]["additional_evidence"][0]["quote"] = "A fabricated comparison quotation"
    assert validated_candidates(value, sources, "compare") == ([], [])


@pytest.mark.asyncio
async def test_semantic_repair_is_reaudited_before_display():
    rejected = {
        **audit(),
        "answerable": False,
        "issues": ["Recap used instead of operative instruction"],
    }
    complete = AsyncMock(
        side_effect=[
            json.dumps(draft()),
            json.dumps(rejected),
            json.dumps(draft()),
            json.dumps(audit()),
        ]
    )
    result = await answer("STR deadline?", {"sources": [source()]}, complete)
    assert not result["knowledge_gap"]
    assert complete.call_count == 4


@pytest.mark.asyncio
async def test_full_documents_are_not_repeated_per_chunk():
    first = {**source(), "full_document": True, "full_text": "Full document text"}
    second = {**first, "chunk_id": "second"}
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(audit())])
    await answer("STR deadline?", {"sources": [first, second]}, complete)
    payload = json.loads(complete.call_args_list[0].args[0])
    assert payload["full_documents"] == {"real_document": "Full document text"}
    assert all("full_text" not in row for row in payload["evidence"])


@pytest.mark.asyncio
async def test_success_uses_strict_schema_and_no_rewrite():
    complete = AsyncMock(side_effect=[json.dumps(draft()), json.dumps(audit())])
    result = await answer(
        "STR deadline?", {"sources": [source()], "knowledge_gap": False}, complete
    )
    assert not result["knowledge_gap"]
    assert len(result["citations"]) == 1
    assert complete.call_count == 2
    assert all(
        call.kwargs["json_schema"]["additionalProperties"] is False
        for call in complete.call_args_list
    )


@pytest.mark.asyncio
async def test_gap_does_not_call_model_or_invent_inventory():
    complete = AsyncMock()
    result = await answer("Absent document?", {"sources": [], "knowledge_gap": True}, complete)
    assert result == gap()
    complete.assert_not_called()
    assert "vendor contracts" not in result["answer"]


@pytest.mark.asyncio
async def test_invalid_json_never_becomes_displayed_prose():
    complete = AsyncMock(return_value='{"answerable":true,"claims":[')
    result = await answer("test", {"sources": [source()]}, complete)
    assert result["citations"] == []
    assert '"claims"' not in result["answer"]


@pytest.mark.asyncio
async def test_rewrite_cannot_modify_a_grounded_result():
    from services.boardroom_formatter import BoardroomFormatter

    result = render(
        *validated_candidates(draft(), {"real_chunk": source()}, "test"), {"real_chunk": source()}
    )
    assert await BoardroomFormatter().format_executive_summary(result) is result


@pytest.mark.asyncio
async def test_stream_and_normal_share_the_same_verified_answer(monkeypatch):
    from agents.strategist import StrategistAgent

    monkeypatch.setattr(
        StrategistAgent,
        "_llm_classify",
        AsyncMock(return_value={"intent": "document_query", "topic": "test"}),
    )
    expected = render(
        *validated_candidates(draft(), {"real_chunk": source()}, "test"), {"real_chunk": source()}
    )
    monkeypatch.setattr(StrategistAgent, "_orchestrate_agents", AsyncMock(return_value=expected))
    agent = StrategistAgent()
    normal = json.loads(await agent.investigate("test"))
    events = [e async for e in agent.investigate_stream("test")]
    assert events[-1]["answer"] == normal["answer"]
    assert events[-1]["citations"] == normal["citations"]
    assert "".join(e["content"] for e in events if e["type"] == "token") == normal["answer"]
    assert normal["verdict"] == "MONITOR"


@pytest.mark.parametrize(
    "query",
    [
        "What is a new customer in the reporting template?",
        "Compare suspicious transaction deadlines in the two circulars",
        "From the letter, what penalty is stated?",
        "How does section 7.6 of the cybersecurity framework work?",
    ],
)
def test_document_references_override_operational_keywords(query):
    from agents.strategist import StrategistAgent

    assert StrategistAgent()._heuristic_classify(query)["intent"] == "document_query"


def test_no_demo_content_even_with_legacy_flags(monkeypatch):
    from agents.researcher import ResearcherAgent
    from agents.strategist import StrategistAgent
    from agents.watchdog import WatchdogAgent
    from services.demo_seed import seed_demo_data
    from services.fraud_service import get_fraud_signals
    from services.regulatory_service import get_regulatory_context

    monkeypatch.setenv("DEMO_CANNED_SCENARIOS", "true")
    assert StrategistAgent()._match_canned_scenario("CBN compliance status") is None
    assert json.loads(ResearcherAgent()._mock_search("test"))["results"] == []
    assert json.loads(ResearcherAgent()._mock_document_list())["documents"] == []
    assert WatchdogAgent()._seed_regulatory_alerts() == []
    assert get_fraud_signals() == []
    assert get_regulatory_context("AML penalty")["knowledge_gap"]
    assert seed_demo_data(force=True)["seeded"] is False
    from services.cbn_regulations import CBN_REGULATIONS, DEMO_FINTECH_ENTITIES
    from services.web_intelligence import _mock_signals

    assert CBN_REGULATIONS == DEMO_FINTECH_ENTITIES == []
    assert _mock_signals()["regulatory"] == []


@pytest.mark.parametrize(
    "flags,count,expected",
    [
        ([True], 1, True),
        ([1], 1, False),
        ([False], 1, False),
        ([], 1, False),
        ([], 0, True),
        (None, 0, False),
    ],
)
def test_audit_flags_require_actual_booleans(flags, count, expected):
    assert audit_flags(flags, count) is expected
