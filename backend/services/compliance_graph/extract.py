"""
Model-assisted extraction, constrained so the model can only point at text.

The model classifies numbered candidate sentences that segment.py found in the
document and returns short spans. Every span must be an exact substring of its
own candidate (common.locate); anything else is dropped. Quotes always come
from the candidate itself, never from the model. A malformed reply shrinks the
batch (halves it, then skips it) instead of failing the job.
"""

from __future__ import annotations

import json
import logging
import re

from services.compliance_graph import taxonomy
from services.compliance_graph.common import exact_span
from services.compliance_graph.deadlines import FREQUENCIES
from services.compliance_graph.llm import ask_json

logger = logging.getLogger(__name__)

STRING = {"type": "string"}
NULLABLE_STRING = {"type": ["string", "null"]}
BOOL = {"type": "boolean"}


def _schema(properties):
    from services.grounded_answers import object_schema

    return object_schema(properties)


def _nullable_enum(values):
    return {"anyOf": [{"type": "string", "enum": list(values)}, {"type": "null"}]}


TOPIC_ARRAY = {"type": "array", "items": {"type": "string", "enum": list(taxonomy.TOPICS)}}
CATEGORY_ARRAY = {"type": "array", "items": {"type": "string",
                                             "enum": list(taxonomy.CATEGORIES) + list(taxonomy.GROUPS)}}
ROLES = ("regulation", "policy", "procedure", "evidence_record", "other")


def _clip(text: str | None, limit: int) -> str | None:
    if not isinstance(text, str):
        return None
    text = " ".join(text.split())
    return text[:limit].rstrip() if text else None


def _span(value, candidate_text: str) -> str | None:
    """The model's span, verbatim from the candidate, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    return exact_span(value, candidate_text)


def _payload_candidates(batch, sentences_by_index):
    out = []
    for s in batch:
        before = sentences_by_index.get(s.index - 1)
        after = sentences_by_index.get(s.index + 1)
        item = {
            "id": f"c{s.index}",
            "text": s.quote,
            "before": before.quote[:400] if before else "",
            "after": after.quote[:400] if after else "",
        }
        lead = sentences_by_index.get(s.lead_in) if getattr(s, "lead_in", None) is not None else None
        if lead is not None and lead is not before:
            item["lead_in"] = lead.quote[:400]
        out.append(item)
    return out


async def _classify(db, batch, call, verify, *, min_batch=1):
    """Run call(batch) -> raw dict; verify(raw, batch) -> list. Halves the batch on unusable replies."""
    raw = await call(batch)
    if raw is not None and isinstance(raw.get("items"), list):
        return verify(raw, batch)
    if len(batch) <= min_batch:
        logger.warning("Graph extraction: skipped %d candidate(s) after an unusable model reply", len(batch))
        return []
    middle = len(batch) // 2
    return (await _classify(db, batch[:middle], call, verify, min_batch=min_batch)
            + await _classify(db, batch[middle:], call, verify, min_batch=min_batch))


# ─── Document role ───────────────────────────────────────────────────────────

ROLE_SYSTEM = (
    "Classify one document a Nigerian financial institution uploaded to its compliance workspace. "
    "regulation: issued by a regulator or the legislature (circular, guideline, framework, Act, regulation). "
    "policy: the institution's own policy or framework stating what it commits to. "
    "procedure: the institution's own step-by-step procedure or manual. "
    "evidence_record: a record showing something was done (register, log, report, minutes, attestation, "
    "training record, return acknowledgement). other: anything else. "
    "reason_span: a few exact words from the text that show it, or null."
)
ROLE_SCHEMA_PROPS = {"role": {"type": "string", "enum": list(ROLES)}, "reason_span": NULLABLE_STRING}

_ROLE_HINTS = (
    ("evidence_record", r"\b(?:register|log|minutes|attendance|report|attestation|certificate|acknowledg\w+|receipt|"
                        r"sign[-\s]?off|checklist|returns?\s+submitted|evidence)\b"),
    ("procedure", r"\b(?:procedures?|manual|process|playbook|sop|standard\s+operating)\b"),
    ("policy", r"\b(?:policy|policies|framework|charter|code\s+of\s+conduct)\b"),
    ("regulation", r"\b(?:circular|guidelines?|regulations?|act\s+\d{4}|letter\s+to\s+all|directive|cbn|nfiu|ndic|ndpc|"
                   r"sec\b|exposure\s+draft)\b"),
)


def role_hint(title: str | None, filename: str | None = None) -> str | None:
    """A deterministic first guess from the title or filename (the upload dialog uses the same rules)."""
    text = f"{title or ''} {filename or ''}".lower()
    for role, pattern in _ROLE_HINTS:
        if re.search(pattern, text):
            return role
    return None


async def suggest_role(db, *, workspace_id, title, opening_text, complete=None, usage=None) -> dict | None:
    prompt = json.dumps({"title": title or "", "opening_text": (opening_text or "")[:2500]}, ensure_ascii=False)
    raw = await ask_json(db, workspace_id=workspace_id, prompt=prompt, system=ROLE_SYSTEM,
                         schema=_schema(ROLE_SCHEMA_PROPS), max_tokens=120, complete=complete, usage=usage)
    if not raw or raw.get("role") not in ROLES:
        return None
    return {"role": raw["role"], "reason": exact_span(raw.get("reason_span"), opening_text or "")}


# ─── Requirements in regulations ─────────────────────────────────────────────

REQUIREMENTS_SYSTEM = (
    "You read candidate sentences from a Nigerian financial regulator's document (a CBN circular, guideline, "
    "framework or an Act) and decide which ones impose a requirement on regulated institutions.\n"
    "For every candidate return one item:\n"
    "- is_requirement: true only when the sentence itself obliges, prohibits or expects something of regulated "
    "institutions, their boards or staff. False for background, definitions, observations, history, what the "
    "regulator itself will do, and penalties alone.\n"
    "- kind: obligation, prohibition, expectation (for should / are expected to), or none.\n"
    "- addressee_span: the exact words in the candidate that name who must act, or null.\n"
    "- summary: at most 30 words stating the duty in plain English. Add no facts, dates or penalties the "
    "sentence does not state. Never say whether anyone complies.\n"
    "- deadline_span: the exact words stating when or how often it must be done, or null.\n"
    "- effective_span: the exact words stating when the requirement starts, or null.\n"
    "- frequency: how often it recurs, or null.\n"
    "- topics: up to three topic codes.\n"
    "- categories: licence category codes the candidate itself names; otherwise an empty list.\n"
    "A candidate that is a list item completes the sentence that introduces the list (`lead_in`, or `before` "
    "for the first item): judge the item as that whole duty. When the introduction only recalls what an "
    "earlier circular required (\"in which all OFIs were required to\"), the items are history, not "
    "requirements of this document.\n"
    "Copy spans character for character from the candidate's own text. The before/after/lead_in sentences are "
    "context only; never copy spans from them."
)


def requirements_schema():
    return _schema({"items": {"type": "array", "items": _schema({
        "id": STRING,
        "is_requirement": BOOL,
        "kind": {"type": "string", "enum": ["obligation", "prohibition", "expectation", "none"]},
        "addressee_span": NULLABLE_STRING,
        "summary": STRING,
        "deadline_span": NULLABLE_STRING,
        "effective_span": NULLABLE_STRING,
        "frequency": _nullable_enum(FREQUENCIES),
        "topics": TOPIC_ARRAY,
        "categories": CATEGORY_ARRAY,
    })}})


def verify_requirements(raw, batch) -> list[dict]:
    by_id = {f"c{s.index}": s for s in batch}
    out, seen = [], set()
    for item in raw.get("items", []):
        if not isinstance(item, dict):
            continue
        sentence = by_id.get(item.get("id"))
        if sentence is None or item["id"] in seen:
            continue
        seen.add(item["id"])
        if item.get("is_requirement") is not True or item.get("kind") not in ("obligation", "prohibition", "expectation"):
            continue
        text = sentence.quote
        out.append({
            "sentence": sentence,
            "kind": item["kind"],
            "summary": _clip(item.get("summary"), 300),
            "addressee_span": _span(item.get("addressee_span"), text),
            "deadline_span": _span(item.get("deadline_span"), text),
            "effective_span": _span(item.get("effective_span"), text),
            "frequency": item.get("frequency") if item.get("frequency") in FREQUENCIES else None,
            "topics": taxonomy.valid_topics(item.get("topics")),
            "categories": taxonomy.valid_codes(item.get("categories")),
        })
    return out


async def classify_requirements(db, batch, sentences_by_index, *, workspace_id, title, regulator,
                                complete=None, usage=None) -> list[dict]:
    async def call(part):
        prompt = json.dumps({
            "document": {"title": title or "", "regulator": regulator or ""},
            "topics": taxonomy.TOPICS,
            "categories": {code: taxonomy.label(code) for code in list(taxonomy.CATEGORIES) + list(taxonomy.GROUPS)},
            "candidates": _payload_candidates(part, sentences_by_index),
        }, ensure_ascii=False)
        return await ask_json(db, workspace_id=workspace_id, prompt=prompt, system=REQUIREMENTS_SYSTEM,
                              schema=requirements_schema(), max_tokens=140 * len(part) + 200,
                              complete=complete, usage=usage)

    return await _classify(db, batch, call, verify_requirements)


# ─── Controls in policies and procedures ─────────────────────────────────────

CONTROLS_SYSTEM = (
    "You read candidate sentences from a Nigerian financial institution's own policy or procedure and decide "
    "which describe a control: a specific activity the institution commits to perform (who does what, when or "
    "how often), such as reviews, approvals, checks, screenings, reconciliations, reports or trainings.\n"
    "For every candidate return one item:\n"
    "- is_control: false for aims, principles, definitions and background.\n"
    "- name: at most 8 words naming the control.\n"
    "- summary: at most 30 words describing what is done. Add nothing the sentence does not say. Never say "
    "whether the control complies with anything.\n"
    "- performer_span: the exact words naming who performs it, or null.\n"
    "- frequency: how often it runs, or null.\n"
    "- evidence_expected: at most 15 words naming the record it would produce, or null.\n"
    "- topics: up to three topic codes.\n"
    "Copy spans character for character from the candidate's own text."
)


def controls_schema():
    return _schema({"items": {"type": "array", "items": _schema({
        "id": STRING,
        "is_control": BOOL,
        "name": STRING,
        "summary": STRING,
        "performer_span": NULLABLE_STRING,
        "frequency": _nullable_enum(FREQUENCIES),
        "evidence_expected": NULLABLE_STRING,
        "topics": TOPIC_ARRAY,
    })}})


def verify_controls(raw, batch) -> list[dict]:
    by_id = {f"c{s.index}": s for s in batch}
    out, seen = [], set()
    for item in raw.get("items", []):
        if not isinstance(item, dict):
            continue
        sentence = by_id.get(item.get("id"))
        if sentence is None or item["id"] in seen or item.get("is_control") is not True:
            continue
        seen.add(item["id"])
        name = _clip(item.get("name"), 80)
        if not name:
            continue
        out.append({
            "sentence": sentence,
            "name": name,
            "summary": _clip(item.get("summary"), 300),
            "performer_span": _span(item.get("performer_span"), sentence.quote),
            "frequency": item.get("frequency") if item.get("frequency") in FREQUENCIES else None,
            "evidence_expected": _clip(item.get("evidence_expected"), 160),
            "topics": taxonomy.valid_topics(item.get("topics")),
        })
    return out


async def classify_controls(db, batch, sentences_by_index, *, workspace_id, title, complete=None, usage=None):
    async def call(part):
        prompt = json.dumps({
            "document": {"title": title or ""},
            "topics": taxonomy.TOPICS,
            "candidates": _payload_candidates(part, sentences_by_index),
        }, ensure_ascii=False)
        return await ask_json(db, workspace_id=workspace_id, prompt=prompt, system=CONTROLS_SYSTEM,
                              schema=controls_schema(), max_tokens=130 * len(part) + 200,
                              complete=complete, usage=usage)

    return await _classify(db, batch, call, verify_controls)


# Sentences in internal documents that may describe a control.
CONTROL_CUES = re.compile(
    r"\b(?:shall|must|will|is\s+responsible|are\s+responsible|responsible\s+for|ensure|review\w*|approv\w*|"
    r"monitor\w*|screen\w*|reconcil\w*|report\w*|verif\w*|check\w*|train\w*|escalat\w*|maintain\w*|"
    r"daily|weekly|monthly|quarterly|annually|every)\b",
    re.I,
)


# ─── Evidence records ────────────────────────────────────────────────────────

EVIDENCE_SYSTEM = (
    "You read the opening of a record a Nigerian financial institution keeps as evidence (a register, log, "
    "report, minutes, attestation or similar). Say what activity it records and for which period.\n"
    "- activity: at most 30 words describing what the record shows was done. Never say whether anything "
    "complies.\n"
    "- activity_span: exact words from the text that show the activity, or null.\n"
    "- period_span: exact words stating the period it covers, or null.\n"
    "- record_date_span: exact words stating when the record was made or signed, or null.\n"
    "- topics: up to three topic codes.\n"
    "Copy spans character for character from the text."
)


def evidence_schema():
    return _schema({
        "activity": STRING,
        "activity_span": NULLABLE_STRING,
        "period_span": NULLABLE_STRING,
        "record_date_span": NULLABLE_STRING,
        "topics": TOPIC_ARRAY,
    })


async def describe_evidence(db, *, workspace_id, title, text, complete=None, usage=None) -> dict | None:
    opening = (text or "")[:8000]
    prompt = json.dumps({"title": title or "", "topics": taxonomy.TOPICS, "text": opening}, ensure_ascii=False)
    raw = await ask_json(db, workspace_id=workspace_id, prompt=prompt, system=EVIDENCE_SYSTEM,
                         schema=evidence_schema(), max_tokens=260, complete=complete, usage=usage)
    if not raw:
        return None
    return {
        "activity": _clip(raw.get("activity"), 300),
        "activity_span": exact_span(raw.get("activity_span"), opening),
        "period_span": exact_span(raw.get("period_span"), opening),
        "record_date_span": exact_span(raw.get("record_date_span"), opening),
        "topics": taxonomy.valid_topics(raw.get("topics")),
    }
