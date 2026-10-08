"""Conversation routing regressions; no database, network, or model credentials."""

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from services.chat_intent import conversational_kind
from services.chat_router import MAX_CONTEXT_CHARS, conversation_context, heuristic_route, route_question


def turn(question="What CBN capital requirements apply to an MFB?", **extras):
    return {"question": question, "answer_summary": "Supported findings and their limitations.",
            "intent": "regulatory_compliance", **extras}


def selection(intent="document_query", reference=None, title=None, missing="none"):
    return {"intent": intent, "reference_turn": reference, "source_title_index": title, "missing": missing}


@pytest.mark.parametrize("question", [
    "ok thats nice", "Okay, that's helpful, thanks!", "Thanks so much Iroko", "Hi Iroko",
    "Hello, how are you?", "I'm fine, thanks", "I’m doing well", "What can you do?", "Bye!",
])
async def test_whole_conversational_messages_do_not_call_model(question):
    # "I'm doing well" is a normal conversational phrase, not a factual fine query.
    complete = AsyncMock()
    result = await route_question(question, [turn()], complete)
    assert result["intent"] == "greeting"
    assert result["clarification"] is None
    complete.assert_not_called()


@pytest.mark.parametrize("question", [
    "Hi, what is the CBN penalty for failing reporting requirements?",
    "Thanks, compare the NDPC requirements with CBN requirements.",
    "Good morning, how much is the fine?",
    "Okay that's nice, but what does the circular require?",
])
async def test_mixed_greeting_and_question_always_enters_factual_route(question):
    complete = AsyncMock()
    result = await route_question(question, complete=complete)
    assert conversational_kind(question) is None
    assert result["intent"] in {"regulatory_compliance", "document_query"}
    assert result["query"] == question
    complete.assert_not_called()


def test_mixed_greeting_with_unidentified_breach_asks_a_focused_question():
    result = heuristic_route("Hi, what is the CBN penalty for this breach?")
    assert result["intent"] == "clarification"
    assert "Which rule" in result["clarification"]


@pytest.mark.parametrize("question,expected", [
    ("What are the penalties for failing CBN reporting requirements?", "regulatory_compliance"),
    ("What are the latest compliance risks for a fintech?", "regulatory_compliance"),
    ("Check the SLA penalties in our contract", "document_query"),
    ("From the letter, what penalty is stated?", "document_query"),
    ("What CBN fine is stated in the uploaded letter?", "document_query"),
    ("What does the letter state about CBN penalties?", "document_query"),
    ("What was last month's system uptime?", "network_operations"),
    ("Investigate these suspicious transactions", "fraud_intelligence"),
    ("Summarise customer complaints this month", "customer_complaint"),
    ("Summarise the uploaded annual report", "document_query"),
    ("Tell me a joke", "out_of_domain"),
])
async def test_clear_subjects_are_routed_without_a_model(question, expected):
    complete = AsyncMock()
    assert (await route_question(question, complete=complete))["intent"] == expected
    complete.assert_not_called()


@pytest.mark.parametrize("question", ["Continue", "Does that apply to our MFB?", "Expand on that", "₦14 million?!"])
async def test_missing_reference_requests_clarification_without_model(question):
    complete = AsyncMock()
    result = await route_question(question, complete=complete)
    assert result["intent"] == "clarification"
    assert result["clarification"]
    complete.assert_not_called()


@pytest.mark.parametrize("question", [
    "In the May 2, 2017 AML/CFT rendition circular, which organisation receives Suspicious "
    "Transaction Reports and how soon must they be submitted?",
    "Who receives suspicious transaction reports and when are they due?",
    "We received the CBN letter on BVN enrolment; does it apply to microfinance banks?",
    "In section 7.6 of the cybersecurity framework, by when must it be reported?",
    "The circular sets a deadline; does this circular apply to unit MFBs?",
])
@pytest.mark.parametrize("history", [[], [turn()]])
def test_pronoun_naming_its_own_subject_is_a_new_question(question, history):
    result = heuristic_route(question, history)
    assert result["intent"] not in {"clarification", "follow_up"}
    assert result["query"] == question


@pytest.mark.parametrize("question", [
    "Does that apply to our MFB?", "Hi, what is the CBN penalty for this breach?",
    "Explain that rule", "Is this still current?", "What is the fine for it?",
    "Can you explain that?", "Do these requirements apply to us?",
])
def test_dangling_reference_still_needs_an_earlier_turn(question):
    assert heuristic_route(question)["intent"] == "clarification"
    followup = heuristic_route(question, [turn()])
    assert followup["intent"] == "follow_up"
    assert followup["query"].startswith("What CBN capital requirements")


UNINSURED = turn("Tell me about the CBN letter on investments with uninsured entities.")
EVALS = Path(__file__).resolve().parent / "evals"


def test_no_self_contained_evaluation_question_is_refused_or_rerouted():
    """Every graded and synthetic question names its subject; none may be sent back."""
    questions = [c["question"] for name in ("cbn_document_questions.json", "cbn_retrieval_questions.json")
                 for c in json.loads((EVALS / name).read_text(encoding="utf-8"))]
    routed = {q: heuristic_route(q)["intent"] for q in questions}
    assert len(questions) > 150
    assert {q: i for q, i in routed.items() if i not in {"regulatory_compliance", "document_query"}} == {}


@pytest.mark.parametrize("question", [
    "STR deadline?", "What is the CTR deadline?", "When are FTRs due?",
    "When was the deadline for 2019 audited financial statements pushed to?",
    "Abeg, who we go send STR give and how fast e suppose reach?",
])
async def test_compliance_shorthand_is_answered_without_a_model(question):
    complete = AsyncMock()
    result = await route_question(question, complete=complete)
    assert result["intent"] in {"regulatory_compliance", "document_query"}
    assert result["query"] == question
    complete.assert_not_called()


async def test_model_cannot_send_back_a_question_that_names_its_subject():
    complete = AsyncMock(return_value=json.dumps(selection("clarification", missing="topic")))
    question = "How often must the board be briefed on cyber risk?"  # No routing keywords.
    result = await route_question(question, complete=complete)
    assert result["intent"] == "document_query"
    assert result["query"] == question
    complete.assert_awaited_once()


@pytest.mark.parametrize("question", ["Who receives those?", "Where do we submit them?", "What does that mean?",
                                      "What does its section 7 require?"])
def test_pronoun_after_a_common_verb_points_back(question):
    assert heuristic_route(question)["intent"] == "clarification"
    result = heuristic_route(question, [turn()])
    assert result["intent"] == "follow_up"
    assert result["query"].startswith("What CBN capital requirements")


@pytest.mark.parametrize("question", [
    "Is there a fine for not complying?", "Under which law?", "What happens if we miss the deadline?",
    "Are there exceptions?", "What is the deadline?",
])
def test_question_with_nothing_specific_continues_the_topic(question):
    result = heuristic_route(question, [UNINSURED])
    assert result["intent"] == "follow_up"
    assert result["query"].startswith(UNINSURED["question"])
    alone = heuristic_route(question)
    assert alone["intent"] == "clarification"
    assert "Which rule" in alone["clarification"]


@pytest.mark.parametrize("question", ["And for MFBs?", "And for currency transaction reports?", "Also for BDCs?"])
def test_and_for_continues_the_topic_even_with_a_keyword(question):
    result = heuristic_route(question, [UNINSURED])
    assert result["intent"] == "follow_up"
    assert result["query"].startswith(UNINSURED["question"])


@pytest.mark.parametrize("question", [
    "STR deadline?", "What leverage ratio must DFIs maintain?", "What fine applies to unit MFBs?",
    "Good morning, how much is the fine?",
])
def test_question_naming_its_own_subject_stays_standalone(question):
    result = heuristic_route(question, [UNINSURED])
    assert result["intent"] != "follow_up"
    assert result["query"] == question


def test_followup_chain_remembers_topic_and_user_scope_without_growing_query():
    history = [turn()]
    scope = heuristic_route("We are a state MFB", history)
    assert scope["intent"] == "follow_up"
    assert "What CBN capital requirements" in scope["query"]
    history.append(turn("We are a state MFB", intent="follow_up", resolved_question=scope["query"]))
    for _ in range(8):
        result = heuristic_route("Tell me more", history)
        assert result["intent"] == "follow_up"
        assert result["query"].count("Follow-up:") == 1
        assert "We are a state MFB" in result["query"]
        assert "What CBN capital requirements" in result["query"]
        history.append(turn("Tell me more", intent="follow_up", resolved_question=result["query"]))
    assert len(result["query"]) < 350


@pytest.mark.parametrize("extra", [
    turn("Does that apply?", intent="clarification"),
    turn("Does that apply?", intent="clarification", resolved_question="Should not become an anchor"),
    turn("Thanks", intent="greeting", resolved_question="Thanks"),
    turn("Tell me a joke", intent="out_of_domain"),
    {"question": "Does that apply?", "answer_summary": "Which rule do you mean?"},
])
def test_nonfactual_turns_cannot_replace_a_valid_topic(extra):
    result = heuristic_route("Tell me more", [turn(), extra])
    assert result["intent"] == "follow_up"
    assert result["query"].startswith("What CBN capital requirements")
    assert heuristic_route("Tell me more", [extra])["intent"] == "clarification"


async def test_explicit_topic_switch_does_not_reuse_old_question():
    complete = AsyncMock()
    question = "Different question: what are NDPC breach notification deadlines?"
    result = await route_question(question, [turn()], complete)
    assert result["intent"] == "regulatory_compliance"
    assert result["query"] == question
    complete.assert_not_called()


async def test_model_can_recognise_a_new_named_subject_after_conversational_prefix():
    complete = AsyncMock(return_value=json.dumps(selection("regulatory_compliance")))
    question = "And what are the NDPC breach notification deadlines?"
    result = await route_question(question, [turn()], complete)
    assert result["intent"] == "regulatory_compliance"
    assert result["query"] == question
    complete.assert_awaited_once()


async def test_self_contained_prefix_does_not_require_nonexistent_history():
    complete = AsyncMock()
    result = await route_question("What about CBN capital requirements?", complete=complete)
    assert result["intent"] == "regulatory_compliance"
    complete.assert_not_called()


async def test_model_resolves_only_existing_turn_and_exact_source_title():
    history = [turn(citations=[{"document_title": "Capital requirements circular"}]),
               turn("What are privacy obligations?", citations=[{"document_title": "Privacy Act"}])]
    complete = AsyncMock(return_value=json.dumps(selection("follow_up", 0, 0)))
    result = await route_question("Does the first one apply to our bank?", history, complete)
    assert result["query"].startswith(history[0]["question"])
    assert "Previously mentioned source to retrieve again: Capital requirements circular" in result["query"]
    assert "Privacy Act" not in result["query"]
    complete.assert_awaited_once()


@pytest.mark.parametrize("invalid", [
    "not JSON", "[]", {"intent": "greeting"},
    selection(intent=[]), selection(intent={}), selection(missing=[]),
    selection("follow_up", True), selection("follow_up", "0"), selection("follow_up", 0.0),
    selection("follow_up", -1), selection("follow_up", 99), selection("follow_up", None),
    selection("follow_up", 0, True), selection("follow_up", 0, "0"), selection("follow_up", 0, 9),
    selection("clarification", missing="none"), selection(missing="topic"),
    {**selection("follow_up", 0), "rewritten_question": "Invented fine is 9 million"},
])
async def test_malformed_or_invented_model_selections_use_deterministic_fallback(invalid):
    complete = AsyncMock(return_value=invalid)
    question = "Does that apply to our bank?"
    history = [turn(citations=[{"document_title": "Real circular"}])]
    result = await route_question(question, history, complete)
    assert result == heuristic_route(question, history)
    assert "Invented fine" not in result["query"]


async def test_model_cannot_select_clarification_turn_as_an_anchor():
    history = [turn(), turn("Which one?", intent="clarification")]
    complete = AsyncMock(return_value=selection("follow_up", 1))
    result = await route_question("Does that apply?", history, complete)
    assert result["query"].startswith(history[0]["question"])


async def test_model_cannot_erase_a_pronoun_reference():
    complete = AsyncMock(return_value=selection("document_query"))
    result = await route_question("Does that apply to our bank?", [turn()], complete)
    assert result["intent"] == "follow_up"
    assert "What CBN capital requirements" in result["query"]


async def test_unknown_question_gets_one_schema_constrained_classification_call():
    complete = AsyncMock(return_value=selection("customer_complaint"))
    result = await route_question("Why are customers leaving our company?", complete=complete)
    assert result["intent"] == "customer_complaint"
    complete.assert_awaited_once()
    payload = json.loads(complete.call_args.args[0])
    assert payload["question"] == result["query"]
    assert complete.call_args.kwargs["json_schema"]["additionalProperties"] is False


def test_context_is_bounded_typed_and_copies_only_whitelisted_fields():
    history = [turn("Q" * 3000, answer_summary="A" * 3000, resolved_question="R" * 5000,
                    citations=[{"title": "T" * 400, "quote": "OLD_EVIDENCE_DO_NOT_COPY"}],
                    arbitrary_metadata={"token": "DO_NOT_COPY"}) for _ in range(20)]
    original = copy.deepcopy(history)
    history.extend([None, "bad entry", {"question": 123}, {"question": ""}])
    context = conversation_context(history)
    serialized = json.dumps(context, ensure_ascii=False)
    assert len(serialized) <= MAX_CONTEXT_CHARS
    assert "DO_NOT_COPY" not in serialized
    assert context["status"] == "unverified_conversation_context"
    assert [entry["turn_id"] for entry in context["turns"]] == list(range(len(context["turns"])))
    assert all(len(entry["user_question"]) <= 1200 for entry in context["turns"])
    assert history[:20] == original


async def test_classification_failure_falls_back_and_timeout_is_bounded(monkeypatch):
    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    from services import chat_router
    monkeypatch.setattr(chat_router, "ROUTING_TIMEOUT_SECONDS", 0.001)
    question = "Why are customers leaving our company?"
    assert await route_question(question, complete=slow) == heuristic_route(question)
    assert await route_question(question, complete=AsyncMock(side_effect=RuntimeError("upstream"))) == heuristic_route(question)


async def test_cancellation_propagates_instead_of_starting_evidence_work():
    with pytest.raises(asyncio.CancelledError):
        await route_question("Why are customers leaving?", complete=AsyncMock(side_effect=asyncio.CancelledError))
