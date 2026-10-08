"""Exact-evidence checks: accept harmless formatting, still reject invented content."""

import json
from unittest.mock import AsyncMock

import pytest

from services.grounded_answers import answer, canonical_number, clean_quote, number_tokens, validated_candidates

TARGETS = ("Each branch of a microfinance bank should acquire 64 new customers per month. "
           "This translates to 774 new bank accounts per branch per year.")
LETTER = "OFIs shall liquidate existing placements in uninsured entities within 90 days of this letter."


def sources():
    return {
        "targets": {"chunk_id": "targets", "document_id": "inclusion", "title": "Inclusion targets",
                    "content": TARGETS, "provenance": {}},
        "letter": {"chunk_id": "letter", "document_id": "uninsured", "title": "Uninsured placements",
                   "content": LETTER, "provenance": {"published_date": "2023-01-09"}},
    }


def claim(text, quote, chunk="targets", extra=()):
    return {"text": text, "chunk_id": chunk, "quote": quote, "additional_evidence": list(extra)}


def calc(left, operation, right, quote="acquire 64 new customers per month. This translates to 774 new bank accounts"):
    return {"left": left, "operation": operation, "right": right, "chunk_id": "targets", "quote": quote}


def check(claims=(), calculations=(), question="What targets does the letter set?"):
    draft = {"answerable": True, "claims": list(claims), "calculations": list(calculations)}
    return validated_candidates(draft, sources(), question)


@pytest.mark.parametrize("value,expected", [
    ("09", "9"), ("1,000", "1000"), ("0.5", "0.5"), ("0.50", "0.5"), ("7.00", "7"), ("0", "0"), ("2023", "2023"),
])
def test_numbers_compare_by_value(value, expected):
    assert canonical_number(value) == expected


def test_operand_with_trailing_fractional_zeros_matches_its_source():
    rate = {"chunk_id": "rate", "document_id": "charges", "title": "Guide to charges",
            "content": "The maximum fee is 2.50 per cent of the loan amount.", "provenance": {}}
    draft = {"answerable": True, "claims": [], "calculations": [
        {"left": "2.50", "operation": "multiply", "right": "4", "chunk_id": "rate",
         "quote": "The maximum fee is 2.50 per cent of the loan amount."}]}
    _, calculations = validated_candidates(draft, {"rate": rate}, "What is the fee on 4 loans?")
    assert [c["result"] for c in calculations] == ["2.50 × 4 = 10.00"]


def test_iso_date_in_metadata_supports_the_same_date_in_prose():
    assert number_tokens("2023-01-09") >= {"2023", "1", "9"}
    claims, _ = check([claim("The January 9, 2023 letter requires liquidation within 90 days.", LETTER, "letter")])
    assert len(claims) == 1


@pytest.mark.parametrize("wrapped", [
    f"\"{LETTER}\"", f"“{LETTER}”", f"...{LETTER[5:]}", f"…{LETTER[5:-4]}…", f"  '{LETTER}'  ",
])
def test_quotation_marks_and_edge_ellipses_are_presentation(wrapped):
    claims, _ = check([claim("OFIs must liquidate such placements within 90 days.", wrapped, "letter")])
    assert len(claims) == 1
    assert claims[0]["quote"] == clean_quote(wrapped)
    assert claims[0]["quote"] in LETTER


@pytest.mark.parametrize("forged", [
    "\"OFIs shall liquidate all placements within 90 days.\"",  # altered wording
    # Joined passages stay rejected even when every part is verbatim: the elided words
    # can carry a qualifier the reader would never see.
    "OFIs shall liquidate existing placements ... within 90 days of this letter.",
])
def test_altered_or_joined_quote_still_fails(forged):
    claims, _ = check([claim("OFIs must liquidate such placements within 90 days.", forged, "letter")])
    assert claims == []


def test_right_words_cited_to_the_wrong_passage_are_reattributed():
    claims, _ = check([claim("OFIs must liquidate such placements within 90 days.", LETTER, "targets")])
    assert claims[0]["chunk_id"] == "letter"
    assert claims[0]["quote"] == LETTER


LIST = "3\\. Present audited accounts.\n\n4\\. Meet a consolidated leverage ratio of at least 10% [Common Equity: Total\nAssets] at all times."


def leverage_claims(text, quote):
    spv = {"chunk_id": "spv", "document_id": "spv-letter", "title": "SPV letter", "content": LIST, "provenance": {}}
    draft = {"answerable": True, "calculations": [], "claims": [claim(text, quote, "spv")]}
    return validated_candidates(draft, {"spv": spv}, "What leverage ratio applies?")[0]


@pytest.mark.parametrize("quote", [
    "4. Meet a consolidated leverage ratio of at least 10% [Common Equity: Total Assets] at all times.",
    "4\\. Meet a consolidated leverage ratio of at least 10%",
])
def test_markdown_escaped_list_numbers_match_their_plain_quote(quote):
    assert leverage_claims("DFIs must meet a consolidated leverage ratio of at least 10%.", quote)


def test_misquoted_figure_is_replaced_by_the_source_but_a_wrong_claim_still_fails():
    sloppy = "4. Meet a consolidated leverage ratio of at least 12% [Common Equity: Total Assets] at all times."
    accepted = leverage_claims("DFIs must meet a consolidated leverage ratio of at least 10%.", sloppy)
    assert accepted and "at least 10%" in accepted[0]["quote"]  # Users see the true source text.
    assert leverage_claims("DFIs must meet a consolidated leverage ratio of at least 12%.", sloppy) == []


@pytest.mark.parametrize("quote,accepted", [
    ('acquire 64 new customers per month".', True),
    ('This translates to 774 new bank accounts" per branch per year.', True),
    ('acquire "64 new customers" per month', True),
    ('acquire 46 new customers per month".', False),
    ("each branch's target is 64 new customers per month", False),
])
def test_stray_double_quotes_are_ignored_but_words_must_match(quote, accepted):
    claims, _ = check([claim("Each branch should acquire 64 new customers per month.", quote)])
    assert bool(claims) is accepted


def test_comparison_claim_may_use_a_checked_calculation_result():
    comparison = claim("The printed annual figure (774) differs from the calculated annual figure (768).", TARGETS)
    claims, calculations = check([comparison], [calc("64", "multiply", "12")],
                                 question="Multiply the monthly target by 12 and compare it with the annual target.")
    assert [c["result"] for c in calculations] == ["64 × 12 = 768"]
    assert claims and claims[0]["text"].startswith("The printed annual figure (774)")


def test_comparison_claim_cannot_use_an_uncomputed_figure():
    invented = claim("The printed annual figure (774) differs from the expected 770.", TARGETS)
    claims, _ = check([invented], [calc("64", "multiply", "12")],
                      question="Multiply the monthly target by 12 and compare it with the annual target.")
    assert claims == []


@pytest.mark.parametrize("dash", ["-", "–", "—", "−"])
def test_dash_variants_are_the_same_punctuation(dash):
    dated = {"chunk_id": "gazette", "document_id": "gazette", "title": "Gazette",
             "content": "Lagos — 23rd May, 2023. Revocation of operating licences.", "provenance": {}}
    draft = {"answerable": True, "calculations": [], "claims": [
        claim("The gazette is dated in Lagos on 23rd May 2023.", f"Lagos {dash} 23rd May, 2023.", "gazette")]}
    claims, _ = validated_candidates(draft, {"gazette": dated}, "When was it published?")
    assert len(claims) == 1


SCHEDULE = ("WHEREAS: 1. The 47 (forty-seven) Microfinance Banks listed in the Schedule\nhereto have "
            "remained inactive or failed to render returns for more than six (6) months.")


def schedule_claim(quote):
    gazette = {"chunk_id": "si22", "document_id": "si22", "title": "S.I. No. 22", "content": SCHEDULE, "provenance": {}}
    draft = {"answerable": True, "calculations": [], "claims": [
        claim("The Schedule lists 47 microfinance banks that remained inactive.", quote, "si22")]}
    return validated_candidates(draft, {"si22": gazette}, "How many licences were revoked?")[0]


def test_near_exact_misquote_is_aligned_to_the_verbatim_source():
    claims = schedule_claim("The 47 (forty-seven) Microfinance Banks listed in the Schedule thereto have remained inactive")
    assert len(claims) == 1
    assert claims[0]["quote"] == "The 47 (forty-seven) Microfinance Banks listed in the Schedule\nhereto have remained inactive"


@pytest.mark.parametrize("quote", [
    "The 47 (forty-seven) Microfinance Banks listed in the Schedule hereto have not remained inactive",  # negation
    "The 47 banks named in the annex were closed by the regulator after review",  # mostly different words
    "The 47 Microfinance Banks thereto",  # too short to align safely
])
def test_alignment_never_rescues_a_changed_meaning_or_a_loose_paraphrase(quote):
    assert schedule_claim(quote) == []


@pytest.mark.parametrize("quote,expected", [
    ("4.\\. Meet a consolidated leverage ratio", "Meet a consolidated leverage ratio"),
    ("4\\. Meet a consolidated leverage ratio", "Meet a consolidated leverage ratio"),
    ("(iv) Submit returns monthly", "Submit returns monthly"),
    ("a) Submit returns monthly", "Submit returns monthly"),
    ("I am required to submit returns", "I am required to submit returns"),
    ("e.g. returns and reports", "e.g. returns and reports"),
])
def test_leading_list_numbers_are_numbering_not_content(quote, expected):
    assert clean_quote(quote) == expected


def test_cited_table_rows_are_shown_as_readable_text():
    from services.grounded_answers import readable_excerpt

    row = ("<tr> <td>2</td> <td>Suspicious Transaction Reports (STRs)</td> <td>NFIU</td> "
           "<td>Within 24 Hours</td> </tr> <tr> <td>3</td> <td>FTRs</td> <td>CBN &amp; NFIU</td> </tr>")
    assert readable_excerpt(row) == "2 | Suspicious Transaction Reports (STRs) | NFIU | Within 24 Hours\n3 | FTRs | CBN & NFIU"
    assert readable_excerpt("4\\. Meet the ratio <!-- PageNumber=\"3\" --> at all times.") == "4. Meet the ratio at all times."
    assert readable_excerpt(LETTER) == LETTER


def test_figures_absent_from_the_cited_source_still_fail():
    claims, _ = check([claim("The letter sets 64 a month, which is 768 a year.", TARGETS)])
    assert claims == []


def test_chained_calculation_may_use_an_earlier_checked_result():
    _, calculations = check(calculations=[calc("64", "multiply", "* 12"), calc("774", "subtract", "768")],
                            question="Multiply the monthly target by 12 and compare it with the annual target.")
    assert [c["result"] for c in calculations] == ["64 × 12 = 768", "774 − 768 = 6"]


def test_operand_that_is_neither_quoted_asked_nor_computed_fails():
    _, calculations = check(calculations=[calc("64", "multiply", "12"), calc("774", "subtract", "770")],
                            question="Multiply the monthly target by 12.")
    assert [c["result"] for c in calculations] == ["64 × 12 = 768"]


async def test_stray_calculation_verdict_does_not_void_supported_claims():
    draft = {"answerable": True, "missing_information": [], "direct_answer": "", "followup_questions": [],
             "claims": [claim("Each branch should acquire 64 new customers per month.", TARGETS)], "calculations": []}
    audit = {"answerable": True, "issues": [], "supported_claims": [True], "supported_calculations": [True],
             "missing_information": [], "direct_answer_supported": True}
    complete = AsyncMock(side_effect=[json.dumps(draft), json.dumps(audit)])
    result = await answer("What is the monthly target?", {"sources": list(sources().values())}, complete,
                          answer_mode="helpful")
    assert "64 new customers per month" in result["answer"]
    assert result["answer_status"] == "answered"
