"""
Who a requirement is addressed to, and whether that includes a workspace.

Extraction records addressees with their basis:
  * stated     an exact match of an explicit term in the document's own words
               ("TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)", "all MFBs shall").
  * suggested  a typo-tolerant match, a generic term ("banks", "financial
               institutions"), a catalogue title, or the model's reading.
  * inherited  the requirement names no addressee of its own; the document's
               addressees apply.

Applicability for a workspace is computed when asked (never stored as a
verdict) from its declared licence categories, the addressees and any explicit
decision its admins recorded.
"""

from __future__ import annotations

import re

from services.compliance_graph import taxonomy
from services.compliance_graph.segment import addressee_lines, mask_markup

# Subjects that name no one in particular: the document's addressees apply.
_GENERIC_SUBJECT = re.compile(
    r"^(?:all\s+)?(?:you|your\s+(?:institution|bank|organisation|organization)|institutions?|operators?|licensees?|"
    r"each\s+institution|every\s+institution|the\s+institution|management|the\s+board|board\s+of\s+directors)$",
    re.I,
)


def document_addressees(pages, title: str | None = None) -> list[dict]:
    """Addressees from the first page's header lines, then the title (suggested only)."""
    found: list[dict] = []
    for page, start, end, line in addressee_lines(pages):
        exact = taxonomy.match_addressees(line)
        fuzzy = [m for m in taxonomy.fuzzy_addressees(line)
                 if not any(e.explicit and e.start < m.end and m.start < e.end for e in exact)]
        # "MICROFINACE BANKS": the misspelt specific licence outranks the generic "BANKS" inside it.
        exact = [e for e in exact if e.explicit or not any(f.start < e.end and e.start < f.end for f in fuzzy)]
        for m in exact:
            found.append({
                "codes": list(m.codes), "basis": "stated" if m.explicit else "suggested", "term": m.term,
                "quote": line, "span": m.span, "page_position": page.position, "page_number": page.page_number,
                "start": start, "end": end,
            })
        covered = [(m.start, m.end) for m in exact]
        for m in fuzzy:
            if any(a < m.end and m.start < b for a, b in covered):
                continue
            found.append({
                "codes": list(m.codes), "basis": "suggested", "term": m.term, "quote": line, "span": m.span,
                "page_position": page.position, "page_number": page.page_number, "start": start, "end": end,
                "fuzzy": True,
            })
        if found:
            break  # The first header line names the addressees; later ones are subject lines.
    if not found and title:
        for m in taxonomy.match_addressees(title):
            found.append({"codes": list(m.codes), "basis": "suggested", "term": m.term, "quote": title,
                          "span": m.span, "source": "title"})
    return _dedupe(found)


def _dedupe(items: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    rank = {"stated": 0, "suggested": 1}
    for item in items:
        key = tuple(item["codes"])
        if key not in best or rank[item["basis"]] < rank[best[key]["basis"]]:
            best[key] = item
    return list(best.values())


def obligation_addressees(span: str | None) -> tuple[list[str], str | None]:
    """Codes and basis for the words a requirement uses to name who must act."""
    if not span or not span.strip():
        return [], None
    cleaned = " ".join(mask_markup(span).split())
    if _GENERIC_SUBJECT.match(cleaned.strip(" .,:;")):
        return [], None
    matches = taxonomy.match_addressees(cleaned)
    if not matches:
        return [], None
    codes = list(dict.fromkeys(code for m in matches for code in m.codes))
    basis = "stated" if all(m.explicit for m in matches) else "suggested"
    return codes, basis


LABELS = {
    "applies": "Applies to your licence (stated in source)",
    "applies_confirmed": "Applies to your licence (confirmed)",
    "applies_decided": "Marked as applying by your team",
    "likely": "Likely applies — awaiting review",
    "not_addressed": "Not among the stated addressees",
    "not_applicable": "Marked not applicable by your team",
    "undetermined": "Applicability not established",
    "no_profile": "Set your licence categories to see what applies",
}
APPLYING_STATES = ("applies", "applies_confirmed", "applies_decided", "likely")


def evaluate(held_codes, obligation_codes, obligation_basis, document_links, decision=None) -> str:
    """One of LABELS' keys.

    document_links: (codes, basis, review_status) for the document's applies_to
    links; rejected links must be excluded by the caller.
    """
    if decision == "not_applicable":
        return "not_applicable"
    if decision == "applies":
        return "applies_decided"
    held = taxonomy.leaves(held_codes)
    if not held:
        return "no_profile"
    candidates: list[tuple[list[str], str]] = []
    if obligation_codes:
        candidates.append((list(obligation_codes), obligation_basis or "suggested"))
    else:
        for codes, basis, review_status in document_links or ():
            if review_status == "confirmed":
                candidates.append((list(codes), "confirmed"))
            else:
                candidates.append((list(codes), basis))
    if not candidates:
        return "undetermined"
    reliable = [(c, b) for c, b in candidates if b in ("stated", "confirmed")]
    matched_reliable = [b for c, b in reliable if taxonomy.leaves(c) & held]
    if matched_reliable:
        return "applies_confirmed" if "confirmed" in matched_reliable and "stated" not in matched_reliable else "applies"
    if any(taxonomy.leaves(c) & held for c, _b in candidates):
        return "likely"
    if reliable:
        return "not_addressed"
    return "undetermined"
