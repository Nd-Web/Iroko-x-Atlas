"""
Iroko never states a compliance verdict about an organisation from graph data.

A gap reads "Not established in Iroko's records". This screen applies to text
Iroko writes about the organisation (mapping and evidence rationales, record
sentences, coverage labels, chat record answers, the export's status columns).
It does not apply to regulators' own words, which may legitimately say
"in breach".
"""

from __future__ import annotations

import re

NOT_ESTABLISHED = "Not established in Iroko's records"

_VERDICT = re.compile(
    r"\bnon[-\s]?complian(?:t|ce)\b"
    r"|\bnot\s+(?:fully\s+)?compliant\b"
    r"|\b(?:is|are|was|were|be|being|been|fully|partially|now|remains?)\s+compliant\b"
    r"|\bcomplies\s+(?:fully\s+)?with\b"
    r"|\bin\s+breach\b"
    r"|\bviolat(?:e|es|ed|ing|ion|ions)\b",
    re.I,
)


def has_verdict_wording(text: str | None) -> bool:
    return bool(text) and bool(_VERDICT.search(text))


def screen(text: str | None, fallback: str | None = None) -> str | None:
    """The text, or the fallback when it states or implies a compliance verdict."""
    if has_verdict_wording(text):
        return fallback
    return text
