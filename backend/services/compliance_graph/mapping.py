"""
Suggesting how a workspace's controls and evidence relate to requirements.

Candidates come from a local ranking (topic overlap plus BM25 over the
requirement's words and Iroko's summary): no search service, no other
workspace's data. The model then compares texts pairwise and may only point at
words that exist. Every result is a suggestion for a workspace admin to
confirm; judgements are cached by the texts' hashes so unchanged pairs are
never judged (or re-suggested after a rejection) again.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter

from models.compliance_graph import Judgement
from services.compliance_graph.common import PROMPT_VERSIONS, exact_span, stable_id, utcnow
from services.compliance_graph.llm import ask_json
from services.compliance_graph.store import get_current
from services.compliance_graph.wording import screen

TOP_K = 10
_STOP = set("""a an and are as at be been by for from has have in is it its of on or shall should that the their them
then there these this those to was were which will with within must may any all each every such other not no""".split())


def tokens(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if word in _STOP or len(word) < 2:
            continue
        for suffix in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)]
                break
        out.append(word)
    return out


class BM25:
    def __init__(self, documents: dict[str, list[str]], k1: float = 1.4, b: float = 0.75):
        self.documents = documents
        self.k1, self.b = k1, b
        self.lengths = {key: len(words) for key, words in documents.items()}
        self.average = (sum(self.lengths.values()) / len(self.lengths)) if self.lengths else 1.0
        df = Counter(word for words in documents.values() for word in set(words))
        n = len(documents)
        self.idf = {word: math.log(1 + (n - count + 0.5) / (count + 0.5)) for word, count in df.items()}
        self.counts = {key: Counter(words) for key, words in documents.items()}

    def score(self, query: list[str], key: str) -> float:
        counts, length = self.counts[key], self.lengths[key] or 1
        total = 0.0
        for word in set(query):
            if word not in counts:
                continue
            tf = counts[word]
            total += self.idf.get(word, 0.0) * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.average))
        return total


def rank(query_text: str, query_topics, targets: list[dict], k: int = TOP_K) -> list[dict]:
    """targets: dicts with "key", "text" and "topics". Best k with any overlap at all."""
    if not targets:
        return []
    index = BM25({t["key"]: tokens(t["text"]) for t in targets})
    query = tokens(query_text)
    topics = set(query_topics or ())
    scored = []
    for t in targets:
        lexical = index.score(query, t["key"])
        shared = len(topics & set(t.get("topics") or ()))
        score = lexical + 2.5 * shared
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda pair: -pair[0])
    return [t for _s, t in scored[:k]]


# ─── Judgement cache ─────────────────────────────────────────────────────────


def _judgement_id(kind, workspace_id, hash_a, hash_b, version):
    return stable_id("judge", kind, workspace_id, hash_a, hash_b, version)


def cached(db, kind, workspace_id, hash_a, hash_b):
    version = PROMPT_VERSIONS["mapping" if kind == "control" else "evidence_mapping"]
    row = db.get(Judgement, _judgement_id(kind, workspace_id, hash_a, hash_b, version))
    return row.result if row else None


def remember(db, kind, workspace_id, hash_a, hash_b, result):
    version = PROMPT_VERSIONS["mapping" if kind == "control" else "evidence_mapping"]
    jid = _judgement_id(kind, workspace_id, hash_a, hash_b, version)
    if get_current(db, Judgement, jid) is None:
        db.add(Judgement(id=jid, kind=kind, workspace_id=workspace_id, hash_a=hash_a, hash_b=hash_b,
                         prompt_version=version, result=dict(result), created_at=utcnow()))


# ─── Judges ──────────────────────────────────────────────────────────────────

_CONTEXT_RULE = (
    "Each text comes with `context`: the title and section of the document it is in, so \"this policy\" or "
    "\"the framework\" means that document. A match needs the same object, not just the same kind of activity: "
    "reviewing the AML/CFT policy does not address a requirement to review the cybersecurity policy, and "
    "training on one subject does not support a requirement for training on another.\n"
)
CONTROL_JUDGE_SYSTEM = (
    "You compare one control from a Nigerian financial institution's own policy with requirements taken from "
    "regulations. For each requirement decide:\n"
    "- addresses: the control, as written, is the activity the requirement asks for.\n"
    "- partially_addresses: it covers part of what is required.\n"
    "- related_not_addressing: same subject, but it does not do what is required.\n"
    "- unrelated.\n"
    + _CONTEXT_RULE +
    "control_span: exact words from the control that matter, or null. requirement_span: exact words from the "
    "requirement that the control covers, or null. rationale: at most 25 words comparing the two texts. You "
    "only compare texts; never say whether the institution complies."
)
EVIDENCE_JUDGE_SYSTEM = (
    "You compare one record a Nigerian financial institution keeps (what it shows was done, and when) with "
    "controls and requirements. For each target decide:\n"
    "- supports: the record shows the target's activity being carried out.\n"
    "- partially_supports: it shows part of it, or only for part of the period.\n"
    "- related_not_supporting: same subject, but it does not show the activity.\n"
    "- unrelated.\n"
    + _CONTEXT_RULE +
    "record_span: exact words from the record that matter, or null. target_span: exact words from the target, "
    "or null. rationale: at most 25 words. You only compare texts; never say whether the institution complies."
)
_CONTROL_RELATIONS = ["addresses", "partially_addresses", "related_not_addressing", "unrelated"]
_EVIDENCE_RELATIONS = ["supports", "partially_supports", "related_not_supporting", "unrelated"]


def _judge_schema(relations, span_a, span_b):
    from services.grounded_answers import object_schema

    return object_schema({"judgements": {"type": "array", "items": object_schema({
        "target_id": {"type": "string"},
        "relation": {"type": "string", "enum": relations},
        span_a: {"type": ["string", "null"]},
        span_b: {"type": ["string", "null"]},
        "rationale": {"type": "string"},
    })}})


async def judge(db, *, kind, workspace_id, subject, targets, complete=None, usage=None) -> dict[str, dict]:
    """Judge subject (control or evidence) against targets not judged before. Returns target key -> result."""
    results: dict[str, dict] = {}
    pending = []
    for t in targets:
        hit = cached(db, kind, workspace_id, subject["hash"], t["hash"])
        if hit is not None:
            results[t["key"]] = hit
        else:
            pending.append(t)
    if not pending:
        return results
    if kind == "control":
        system, relations, span_a, span_b = CONTROL_JUDGE_SYSTEM, _CONTROL_RELATIONS, "control_span", "requirement_span"
        label = "control"
    else:
        system, relations, span_a, span_b = EVIDENCE_JUDGE_SYSTEM, _EVIDENCE_RELATIONS, "record_span", "target_span"
        label = "record"
    prompt = json.dumps({
        label: {"text": subject["text"], "summary": subject.get("summary") or "", "context": subject.get("context") or ""},
        "targets": [{"id": f"t{i}", "text": t["text"], "summary": t.get("summary") or "", "context": t.get("context") or ""}
                    for i, t in enumerate(pending)],
    }, ensure_ascii=False)
    db.commit()  # never hold locks across the model call
    raw = await ask_json(db, workspace_id=workspace_id, prompt=prompt, system=system,
                         schema=_judge_schema(relations, span_a, span_b), max_tokens=90 * len(pending) + 120,
                         complete=complete, usage=usage)
    items = (raw or {}).get("judgements") if isinstance((raw or {}).get("judgements"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            target = pending[int(str(item.get("target_id", "")).lstrip("t"))]
        except (ValueError, IndexError):
            continue
        if item.get("relation") not in relations:
            continue
        result = {
            "relation": item["relation"],
            "subject_span": exact_span(item.get(span_a), subject["text"]),
            "target_span": exact_span(item.get(span_b), target["text"]),
            "rationale": screen(" ".join(str(item.get("rationale") or "").split())[:240] or None,
                                fallback="Iroko's reasoning was withheld because it used compliance-verdict wording."),
        }
        remember(db, kind, workspace_id, subject["hash"], target["hash"], result)
        results[target["key"]] = result
    return results


POSITIVE = {"addresses": "full", "partially_addresses": "partial", "supports": "full", "partially_supports": "partial"}
