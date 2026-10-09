"""Small shared helpers: feature flag, stable ids, text normalisation, span location, dates."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

# Bump a stage's version when its prompt or schema changes; stored on every row it writes.
PROMPT_VERSIONS = {
    "role": "role-1",
    "requirements": "requirements-2",
    "relations": "relations-2",
    "effective": "effective-2",
    "controls": "controls-1",
    "evidence": "evidence-1",
    "mapping": "mapping-2",
    "evidence_mapping": "evidence-mapping-2",
}

LAGOS = timezone(timedelta(hours=1))  # WAT, no daylight saving

GRAPH_JOB_KINDS = ("graph", "graph_ws")


def enabled() -> bool:
    """COMPLIANCE_GRAPH_ENABLED gates automatic extraction, the worker and chat use."""
    return os.getenv("COMPLIANCE_GRAPH_ENABLED", "false").strip().lower() == "true"


def lagos_today() -> date:
    return datetime.now(LAGOS).date()


def utcnow() -> datetime:
    """Naive UTC, matching every other timestamp column in this codebase."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stable_id(*parts) -> str:
    raw = "\x1f".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


_TRANSLATE = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'", "‐": "-", "‑": "-",
    "‒": "-", "–": "-", "—": "-", "−": "-", " ": " ",
})


def normalize_text(text: str) -> str:
    """Case, quotes, dashes and spacing ignored: the identity of a sentence."""
    text = unicodedata.normalize("NFKC", text or "").translate(_TRANSLATE).casefold()
    return " ".join(re.findall(r"\w+|[^\w\s]", text))


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:32]


def _tokens(text: str):
    text = re.sub(r"<[^>]*>", lambda tag: " " * len(tag.group()), text or "")
    out = []
    for match in re.finditer(r"\w+|[^\w\s]", text):
        token = unicodedata.normalize("NFKC", match.group()).translate(_TRANSLATE).casefold()
        if token not in {'"', "\\", "'"}:
            out.append((token, match.start(), match.end()))
    return out


def locate(span: str | None, text: str) -> tuple[int, int] | None:
    """Character range of span inside text, token by token; None when it is not there.

    Case, quotation marks, dashes and spacing are ignored, nothing else: a span
    the model returns must be words that actually appear, contiguously, in text.
    """
    if not span or not isinstance(span, str):
        return None
    wanted = [t for t, _s, _e in _tokens(span)]
    if not wanted:
        return None
    source = _tokens(text)
    words = [t for t, _s, _e in source]
    n = len(wanted)
    first = wanted[0]
    for i in range(len(words) - n + 1):
        if words[i] == first and words[i:i + n] == wanted:
            return source[i][1], source[i + n - 1][2]
    return None


def exact_span(span: str | None, text: str) -> str | None:
    """The verbatim text of span as it appears in text, or None."""
    where = locate(span, text)
    return text[where[0]:where[1]] if where else None


def parse_iso_date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None
