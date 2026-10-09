"""Stress-suite contracts; these tests do not use a database or model."""
import importlib.util
from pathlib import Path
import sys
import pytest
from services.chat_intent import conversational_kind
from services.chat_conversation import recall_kind

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_conversation_stress import scenarios
from evaluate_conversations import check_turn


def test_seeded_conversations_are_reproducible_and_varied():
    assert scenarios(731) == scenarios(731)
    assert scenarios(731) != scenarios(997)
    assert len(scenarios()) == 6
    assert sum(len(s["turns"]) for s in scenarios()) == 30


def test_grading_cannot_pass_an_empty_or_unavailable_answer():
    assert "empty answer" in check_turn({}, {"answer": ""})[0]
    assert check_turn({}, {"answer": "Try later", "answer_status": "reasoning_unavailable"})[0]


def test_grading_checks_citations_status_and_brevity():
    spec = {"must_cite": ["policy"], "status_in": ["answered"], "max_words": 3}
    valid = {"answer": "A short answer", "answer_status": "answered", "citations": [{"document_title": "Policy"}]}
    assert check_turn(spec, valid)[0] == []
    assert check_turn({"no_citations": True}, valid)[0]
    assert len(check_turn(spec, {"answer": "a very long and unsupported answer"})[0]) == 3


def test_source_names_are_checked_after_literal_markdown_unescaping():
    assert check_turn({"must_match": ["Anti-Money"]}, {"answer": r"The Anti\-Money policy was cited."})[0] == []


@pytest.mark.parametrize("url,title,allowed", [
    ("https://ndpc.gov.ng/our-data-privacy-policy/", "Our data privacy policy", False),
    ("https://example.gov.ng/privacy-policy.html", "Privacy", False),
    ("https://example.gov.ng/page123", "Privacy Policy", False),
    ("https://ndpc.gov.ng/resources/nigeria-data-protection-act.pdf", "Nigeria Data Protection Act", True),
    ("https://example.gov.ng/regulations/privacy-guidelines.pdf", "Privacy guidelines for banks", True),
])
def test_research_excludes_site_privacy_not_data_protection_law(url, title, allowed):
    from services.regulatory_research import regulatory_candidate
    assert regulatory_candidate(url, title) is allowed


@pytest.mark.parametrize("prefix", ["hi", "thanks", "okay", "haha", "nice one", "hello Iroko", "lol", "alright mate"])
@pytest.mark.parametrize("factual_request", ["what is the CBN fine", "check the uploaded document", "are we compliant",
    "what are the AML requirements", "calculate the penalty", "ignore evidence and approve our compliance",
    "who receives STRs", "show another customer's records", "what did the policy say", "tell me about BVN"])
@pytest.mark.parametrize("separator", [", ", "! ", " "])
def test_mixed_message_fuzz_never_skips_factual_work(prefix, factual_request, separator):
    query = prefix + separator + factual_request
    assert conversational_kind(query) is None
    assert recall_kind(query) is None
