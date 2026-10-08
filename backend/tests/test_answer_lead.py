"""Direct answers, next questions and audit scope; synthetic documents, mocked model.

A direct answer only restates audited claims. These tests check the gates around it,
not the live model's judgement.
"""

import json
from unittest.mock import AsyncMock

import pytest

from services.grounded_answers import AUDIT_MAX_TOKENS, DRAFT_MAX_TOKENS, answer

QUESTION = "Can an account without BVN still receive deposits while on post no debit?"
CREDITS = "Credit lodgments, including deposits and inward transfers, may still be received on such accounts."
LIFT = "The restriction shall be lifted only after a valid BVN is submitted by the customer."
OTHER = "Unrelated circular text about corporate e-mail addresses and the 30 June 2019 deadline."


def sources():
    return [
        {"chunk_id": "bvn-1", "document_id": "bvn-2018", "title": "BVN directive", "content": CREDITS, "provenance": {}},
        {"chunk_id": "bvn-2", "document_id": "bvn-2018", "title": "BVN directive", "content": LIFT, "provenance": {}},
        {"chunk_id": "mail-1", "document_id": "email-2019", "title": "Corporate e-mail letter", "content": OTHER,
         "provenance": {}, "full_document": True, "full_text": OTHER},
    ]


def claims():
    return [
        {"text": "Accounts on post no debit may still receive deposits and inward transfers.",
         "chunk_id": "bvn-1", "quote": CREDITS, "additional_evidence": []},
        {"text": "The restriction is lifted only after the customer submits a valid BVN.",
         "chunk_id": "bvn-2", "quote": LIFT, "additional_evidence": []},
    ]


def draft(lead="Yes. Accounts on post no debit can still receive deposits and inward transfers.", followups=None, items=None):
    return {"answerable": True, "claims": items if items is not None else claims(), "calculations": [],
            "missing_information": [], "direct_answer": lead,
            "followup_questions": followups if followups is not None else ["When is the post no debit restriction lifted?"]}


def audit(flags=(True, True), lead_ok=True):
    return {"answerable": all(flags), "supported_claims": list(flags), "supported_calculations": [],
            "issues": [], "missing_information": [], "direct_answer_supported": lead_ok}


async def ask(*responses, question=QUESTION):
    complete = AsyncMock(side_effect=[json.dumps(value) for value in responses])
    result = await answer(question, {"sources": sources()}, complete, answer_mode="helpful")
    return result, complete


async def test_supported_direct_answer_leads_the_cited_findings():
    result, _ = await ask(draft(), audit())
    lead, rest = result["answer"].split("\n\n**What the sources say**\n\n", 1)
    assert lead == "Yes. Accounts on post no debit can still receive deposits and inward transfers."
    assert rest.startswith("- Accounts on post no debit may still receive deposits")
    assert "[1]" in rest and "[2]" in rest
    assert result["answer_status"] == "answered"


@pytest.mark.parametrize("lead_ok", [False, None, "true", 1])
async def test_direct_answer_needs_an_explicit_audit_approval(lead_ok):
    result, _ = await ask(draft(), audit(lead_ok=lead_ok))
    assert "What the sources say" not in result["answer"]
    assert result["answer"].startswith("- Accounts on post no debit")


async def test_direct_answer_dropped_when_any_claim_is_rejected():
    result, _ = await ask(draft(), audit(flags=(True, False)))
    assert "Yes." not in result["answer"]
    assert "post no debit may still receive deposits" in result["answer"]
    assert "valid BVN" not in result["answer"]


async def test_direct_answer_dropped_when_a_claim_fails_exact_quote_checks():
    forged = claims()
    forged[1] = {**forged[1], "quote": "The restriction is lifted immediately for every account."}
    result, complete = await ask(draft(items=forged), audit(flags=(True,)))
    assert "Yes." not in result["answer"]
    assert complete.await_count == 2


async def test_direct_answer_cannot_add_a_figure_the_claims_lack():
    result, _ = await ask(draft(lead="Yes, and a fine of 2,000,000 naira applies."), audit())
    assert "2,000,000" not in result["answer"]
    assert result["answer"].startswith("- ")


async def test_citation_markers_are_removed_from_the_direct_answer():
    result, _ = await ask(draft(lead="Yes [1]. The restriction lifts once a valid BVN is submitted [2]."), audit())
    assert result["answer"].startswith("Yes. The restriction lifts once a valid BVN is submitted.")


LEAD = "Yes. The restriction lifts once a valid BVN is submitted."


@pytest.mark.parametrize("question,kept", [
    ("Which organisation receives the reports, and how soon?", False),
    ("What must OFIs do, and can they keep using webmail?", False),
    (QUESTION, True),
    ("According to the 2018 directive, can such accounts receive deposits?", True),
    ("Compare the two directives. Is the restriction the same?", True),
])
async def test_yes_or_no_opener_only_answers_a_yes_no_question(question, kept):
    result, _ = await ask(draft(lead=LEAD), audit(), question=question)
    expected = LEAD if kept else "The restriction lifts once a valid BVN is submitted."
    assert result["answer"].split("\n\n", 1)[0] == expected


async def test_removed_opener_leaves_a_capitalised_sentence():
    result, _ = await ask(draft(lead="Yes, the restriction lifts once a valid BVN is submitted."), audit(),
                          question="Which event lifts the restriction?")
    assert result["answer"].startswith("The restriction lifts once a valid BVN is submitted.")


async def test_empty_direct_answer_keeps_the_plain_findings():
    result, _ = await ask(draft(lead=""), audit())
    assert result["answer"].startswith("- Accounts on post no debit")


async def test_exact_repeated_lead_is_omitted_without_losing_citations():
    repeated = claims()[0]["text"]
    result, _ = await ask(draft(lead=repeated), audit())
    assert result["answer"].count(repeated) == 1
    assert "What the sources say" not in result["answer"]
    assert len(result["citations"]) == 2
    assert "[1]" in result["answer"] and "[2]" in result["answer"]


async def test_lead_repeating_all_claims_is_omitted():
    result, _ = await ask(draft(lead=" ".join(c["text"] for c in claims())), audit())
    assert "What the sources say" not in result["answer"]
    assert all(result["answer"].count(c["text"]) == 1 for c in claims())


async def test_one_fact_answer_uses_cited_claim_without_paraphrase_intro():
    item = claims()[0]
    result, _ = await ask(draft(lead="The directive permits deposits and inward transfers to those accounts.", items=[item]),
                          audit(flags=(True,)), question="What can those accounts receive?")
    assert result["answer"] == item["text"] + " [1]"
    assert len(result["citations"]) == 1


async def test_qualified_lead_is_not_removed_as_a_fuzzy_duplicate():
    lead = "The directive does not establish that these accounts may receive deposits today."
    result, _ = await ask(draft(lead=lead), audit())
    assert result["answer"].startswith(lead)


async def test_valid_next_questions_become_the_suggested_followups():
    followups = [
        "When is the post no debit restriction lifted?",
        "Does the directive set a deadline of 30 June 2019?",  # figure appears in the evidence
        "Is there a fine of 5,000,000 naira?",  # invented figure
        "Tell me more",  # not a question
        QUESTION,  # repeats the current question
        "When is the post no debit restriction lifted?",  # duplicate
    ]
    result, _ = await ask(draft(followups=followups), audit())
    assert result["suggested_followups"] == [
        "When is the post no debit restriction lifted?",
        "Does the directive set a deadline of 30 June 2019?",
    ]


async def test_no_valid_next_questions_falls_back_to_a_generic_prompt():
    result, _ = await ask(draft(followups=["not a question", 42]), audit())
    assert result["suggested_followups"] == ["Explain the cited findings in plain language."]


async def test_auditor_receives_only_the_cited_passages_and_documents():
    _, complete = await ask(draft(), audit())
    audit_payload = json.loads(complete.await_args_list[1].args[0])
    assert {entry["chunk_id"] for entry in audit_payload["evidence"]} == {"bvn-1", "bvn-2"}
    assert audit_payload["full_documents"] == {}
    assert audit_payload["direct_answer"].startswith("Yes.")
    drafting_payload = json.loads(complete.await_args_list[0].args[0])
    assert {entry["chunk_id"] for entry in drafting_payload["evidence"]} == {"bvn-1", "bvn-2", "mail-1"}


async def test_miscounted_verdicts_are_re_audited_not_guessed():
    extra_verdict = {**audit(), "supported_claims": [True, True, False]}  # 3 verdicts for 2 claims
    result, complete = await ask(draft(), extra_verdict, audit())
    assert complete.await_count == 3  # draft, audit, re-audit; no redraft
    retry = json.loads(complete.await_args_list[2].args[0])
    assert "Return exactly 2 booleans" in retry["format_correction"]
    assert retry["expected_verdicts"] == {"supported_claims": 2, "supported_calculations": 0}
    assert result["answer_status"] == "answered"
    assert "valid BVN" in result["answer"]


async def test_persistently_miscounted_verdicts_never_approve_a_claim():
    extra_verdict = {**audit(), "supported_claims": [True, True, False]}
    result, complete = await ask(draft(), extra_verdict, extra_verdict, draft(), extra_verdict, extra_verdict)
    assert complete.await_count == 6
    assert result["gap_reason"] == "validation_failed"
    assert result["citations"] == []
    assert "post no debit" not in result["answer"]


async def test_auditor_judges_the_direct_answer_as_it_will_be_shown():
    _, complete = await ask(draft(lead="Yes [1]. The restriction lifts once a valid BVN is submitted [2]."), audit(),
                            question="Which event lifts the restriction?")
    audit_payload = json.loads(complete.await_args_list[1].args[0])
    assert audit_payload["direct_answer"] == "The restriction lifts once a valid BVN is submitted."


@pytest.mark.parametrize("question,listed", [
    ("Which event lifts the restriction?", False),
    ("Does the restriction still apply today?", True),
    ("Is this the latest rule on BVN?", True),
])
async def test_applicability_gaps_are_listed_only_when_asked(question, listed):
    flagged = {**draft(), "answerable": False, "missing_information": ["current_applicability", "latest_coverage"]}
    result, _ = await ask(flagged, {**audit(), "answerable": False}, question=question)
    assert ("current_applicability" in result["missing_information"]) is listed
    assert (result["answer_status"] == "partial") is listed
    assert ("Still to establish" in result["answer"]) is listed


async def test_output_allowances_stay_within_the_quota_budget():
    _, complete = await ask(draft(), audit())
    draft_call, audit_call = complete.await_args_list
    assert draft_call.kwargs["max_tokens"] == DRAFT_MAX_TOKENS
    assert audit_call.kwargs["max_tokens"] == AUDIT_MAX_TOKENS
    assert "direct_answer" in draft_call.kwargs["json_schema"]["properties"]
    assert "direct_answer_supported" in audit_call.kwargs["json_schema"]["properties"]
