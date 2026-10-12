"""Normal response-length defaults, with the evidence path still enforced.

These are prompt/plumbing regressions using mocks, not live-model quality claims.
"""

import json
from unittest.mock import AsyncMock

import pytest

from services.chat_conversation import SOCIAL_PROMPT, social_answer
from services.grounded_answers import (
    ANSWER_STYLE,
    HELPFUL_DRAFT_MAX_TOKENS,
    HELPFUL_SYSTEM,
    LEAD_RULES,
    MAX_DIRECT_ANSWER_CHARS,
    SYSTEM,
    answer,
    presentable_lead,
)


def test_grounded_prompt_defaults_to_task_appropriate_detail():
    assert ANSWER_STYLE in SYSTEM and ANSWER_STYLE in HELPFUL_SYSTEM
    assert "Return up to 12 relevant atomic claims" in HELPFUL_SYSTEM
    assert "Return 1-4 relevant atomic facts" not in HELPFUL_SYSTEM
    assert "short-answer preference" in ANSWER_STYLE
    assert "same source support and audit" in ANSWER_STYLE
    assert "one or two plain sentences" not in LEAD_RULES


def test_opening_paragraph_is_not_rejected_for_exceeding_old_brevity_limit():
    lead = "The source describes the reporting process and the records that support it. " * 12
    assert 700 < len(lead) < MAX_DIRECT_ANSWER_CHARS
    assert presentable_lead(lead, "Explain the reporting process") == lead.strip()


def test_opening_paragraph_keeps_a_bounded_safety_ceiling():
    assert presentable_lead("a" * (MAX_DIRECT_ANSWER_CHARS + 1), "Explain it") == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["Explain the policy", "Explain the policy in detail", "Give me a brief policy summary"])
async def test_normal_explanations_have_room_for_text_and_supporting_quotes(question):
    quote = "The compliance team must retain the review records."
    draft = {
        "answerable": True,
        "claims": [{"text": quote, "chunk_id": "policy-1", "quote": quote, "additional_evidence": []}],
        "calculations": [], "missing_information": [], "direct_answer": "", "followup_questions": [],
    }
    audit = {
        "answerable": True, "supported_claims": [True], "supported_calculations": [],
        "issues": [], "missing_information": [], "direct_answer_supported": True,
        "irrelevant_draft_gaps": [],
    }
    complete = AsyncMock(side_effect=[json.dumps(draft), json.dumps(audit)])
    result = await answer(question, {"sources": [{"chunk_id": "policy-1", "document_id": "policy",
        "title": "Synthetic policy", "content": quote, "provenance": {}}]}, complete, answer_mode="helpful")
    assert complete.await_args_list[0].kwargs["max_tokens"] == HELPFUL_DRAFT_MAX_TOKENS
    assert result["answer_status"] == "answered"
    assert quote + " [1]" in result["answer"]
    assert all("**" + heading + "**" in result["answer"] for heading in (
        "What is established", "What is not established", "Needed from you", "Next step"))
    assert complete.await_count == 2  # The independent audit is still required.


@pytest.mark.asyncio
async def test_social_explanation_is_not_limited_to_two_sentences_or_cut_mid_reply():
    reply = "I can help you make sense of a document.\n\n" + (
        "We can discuss its structure, compare passages and prepare a summary for review. " * 17
    ) + "You choose the level of detail."
    assert len(reply) > 1200
    complete = AsyncMock(return_value=json.dumps({"reply": reply, "needs_evidence": False}))
    result = await social_answer("Tell me how you can help", [], complete)
    assert result["answer"] == reply
    assert result["citations"] == []
    assert complete.await_args.kwargs["max_tokens"] == 800
    assert "one or two short sentences" not in SOCIAL_PROMPT


@pytest.mark.asyncio
async def test_longer_conversational_budget_cannot_bypass_factual_research():
    complete = AsyncMock(return_value=json.dumps({"reply": "", "needs_evidence": True}))
    assert await social_answer("Which CBN reporting deadline applies?", [], complete) is None
