"""
services/regulatory_returns/evidence.py

Find answers in the bank's own document library, and draft remediation text.

An answer is accepted only when the model returns a quote that appears,
verbatim, in a document the current user may read (retrieval is workspace-
scoped by services.grounded_answers.retrieve). Anything else is discarded and
the question goes to the officer instead.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Awaitable, Callable

from .assist import hint
from .catalog import Field

logger = logging.getLogger(__name__)

Complete = Callable[..., Awaitable[str]]
Retrieve = Callable[[str], Awaitable[dict]]

_ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["answers"],
    "properties": {"answers": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["key", "found", "value", "quote", "document_id"],
        "properties": {
            "key": {"type": "string"}, "found": {"type": "boolean"}, "value": {"type": "string"},
            "quote": {"type": "string"}, "document_id": {"type": "string"},
        },
    }}},
}

_TYPE_RULES = {
    "date": "a date as YYYY-MM-DD",
    "text": "the exact name or short phrase",
    "textarea": "a concise summary using the document's wording",
    "number": "a number",
    "money": "a number in naira, digits only",
}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _coerce(field: Field, value: str) -> Any:
    v = (value or "").strip()
    if field.type == "date":
        try:
            return date.fromisoformat(v[:10]).isoformat()
        except ValueError:
            return None
    if field.type in ("number", "money"):
        try:
            return float(v.replace(",", "").replace("₦", ""))
        except ValueError:
            return None
    return v or None


async def find_answers(
    return_id: str,
    fields: list[Field],
    period_label: str,
    institution: str,
    retrieve: Retrieve,
    complete: Complete,
) -> dict[str, dict]:
    """key -> {"value", "quote", "document_id", "title"} for answers backed by a quote."""
    wanted = [f for f in fields if hint(return_id, f.key).evidence and f.type in _TYPE_RULES]
    if not wanted:
        return {}
    sources: dict[str, dict] = {}
    for f in wanted:
        try:
            found = await retrieve(f"{hint(return_id, f.key).evidence} {institution}".strip())
        except Exception as exc:
            logger.warning("[evidence] retrieval failed for %s: %s", f.key, exc)
            continue
        for s in found.get("sources", [])[:4]:
            doc_id = s.get("document_id")
            if not doc_id:
                continue
            text = s.get("full_text") or s.get("content") or ""
            entry = sources.setdefault(doc_id, {"title": s.get("title", ""), "text": ""})
            if text and text not in entry["text"]:
                entry["text"] = (entry["text"] + "\n\n" + text)[:9000]
    if not sources:
        return {}
    listing = "\n\n".join(f"[document_id={d}] {v['title']}\n{v['text']}" for d, v in list(sources.items())[:10])
    questions = "\n".join(
        f"- key={f.key}: {f.label} — answer with {_TYPE_RULES[f.type]}" for f in wanted
    )
    prompt = (
        f"These are internal documents of {institution or 'a Nigerian microfinance bank'}. "
        f"The bank is preparing a regulatory return for {period_label}.\n\n{listing}\n\n"
        "For each question, answer ONLY from the documents. Set found=false (empty value, quote and "
        "document_id) unless a single sentence in one document states the answer. When found, copy that "
        "sentence exactly into quote and give its document_id.\n\nQuestions:\n" + questions
    )
    try:
        raw = await complete(prompt, json_schema=_ANSWER_SCHEMA, max_tokens=1500)
        answers = json.loads(raw or "{}").get("answers", [])
    except Exception as exc:
        logger.warning("[evidence] extraction failed: %s", exc)
        return {}
    by_key = {f.key: f for f in wanted}
    out: dict[str, dict] = {}
    for a in answers:
        f = by_key.get(a.get("key"))
        doc = sources.get(a.get("document_id") or "")
        quote = (a.get("quote") or "").strip()
        if not (f and a.get("found") and doc and len(quote) >= 12):
            continue
        if _squash(quote) not in _squash(doc["text"]):
            continue  # not verbatim — never accept an unsupported answer
        value = _coerce(f, a.get("value", ""))
        if value is None:
            continue
        out[f.key] = {"value": value, "quote": quote[:400], "document_id": a["document_id"], "title": doc["title"]}
    return out


async def suggest_remediation(title: str, detail: str, institution: str, letter_date: str, complete: Complete) -> str:
    prompt = (
        f"{institution or 'A Nigerian microfinance bank'} must report this exception to the Central Bank of Nigeria "
        f"in a regulatory return dated {letter_date}:\n\n{title}\n{detail}\n\n"
        "Draft the remediation plan paragraph the bank would include: at most 70 words, formal regulatory English, "
        "first person plural ('The Bank will…'). State the concrete action, the responsible body (e.g. Board Credit "
        "Committee, MD/CEO, Board Risk Committee) and one realistic target date within 30–90 days, written like "
        "'30 November 2026'. Use only the figures given above; do not invent any other facts about the bank. "
        "Return the paragraph only."
    )
    text = await complete(prompt, max_tokens=300)
    return re.sub(r"\s+", " ", (text or "")).strip()
