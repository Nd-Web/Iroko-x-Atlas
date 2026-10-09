"""
Matching items across two versions of a document.

A requirement (or control) keeps its identity across versions when its words
are unchanged (same text hash and occurrence) or nearly unchanged (difflib
ratio >= 0.85 within the same section and a +/-15% position window). Matched
items inherit the earlier lineage, so links, owners and decisions keyed on the
lineage survive; changed wording is reported so the people who rely on it can
re-review.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from services.compliance_graph.common import normalize_text

FUZZY_THRESHOLD = 0.85
POSITION_WINDOW = 0.15


@dataclass
class Item:
    key: str  # id of the row (new items: the id they will get)
    text: str
    text_hash: str
    occurrence: int
    section: str | None
    position: float  # 0..1 through the document
    lineage: str | None = None  # existing lineage (old items)


@dataclass
class Diff:
    unchanged: list[tuple[Item, Item]]  # (old, new)
    modified: list[tuple[Item, Item]]
    added: list[Item]
    removed: list[Item]


def match(old: list[Item], new: list[Item]) -> Diff:
    unchanged, modified = [], []
    taken_old: set[str] = set()
    taken_new: set[str] = set()
    by_identity = {(o.text_hash, o.occurrence): o for o in old}
    for n in new:
        o = by_identity.get((n.text_hash, n.occurrence))
        if o is not None and o.key not in taken_old:
            unchanged.append((o, n))
            taken_old.add(o.key)
            taken_new.add(n.key)
    # Fuzzy: best pairs first, within the same section and a position window.
    candidates = []
    for n in new:
        if n.key in taken_new:
            continue
        norm_n = normalize_text(n.text)
        for o in old:
            if o.key in taken_old:
                continue
            if (o.section or "") != (n.section or "") and o.section and n.section:
                continue
            if abs(o.position - n.position) > POSITION_WINDOW:
                continue
            norm_o = normalize_text(o.text)
            if not norm_o or not norm_n:
                continue
            shorter, longer = sorted((len(norm_o), len(norm_n)))
            if shorter / longer < 0.6:
                continue
            ratio = difflib.SequenceMatcher(None, norm_o, norm_n, autojunk=False).ratio()
            if ratio >= FUZZY_THRESHOLD:
                candidates.append((ratio, o, n))
    for ratio, o, n in sorted(candidates, key=lambda c: -c[0]):
        if o.key in taken_old or n.key in taken_new:
            continue
        modified.append((o, n))
        taken_old.add(o.key)
        taken_new.add(n.key)
    added = [n for n in new if n.key not in taken_new]
    removed = [o for o in old if o.key not in taken_old]
    return Diff(unchanged, modified, added, removed)
