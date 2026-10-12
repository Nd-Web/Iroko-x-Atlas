"""Server-owned completeness and presentation rules, not regulatory answers."""

import re

PARTS = ["capital_requirement", "capital_gap", "deadline"]
PART_LABELS = {
    "capital_requirement": "the applicable capital minimum",
    "capital_gap": "your actual capital gap",
    "deadline": "the applicable deadlines",
}


def requested_parts(question):
    question = question.rsplit("\nFollow-up:", 1)[-1]
    parts = []
    if re.search(r"\bcapital\b", question, re.I) and re.search(
        r"\b(requirements?|minimum|threshold|apply|applies|required)\b", question, re.I
    ):
        parts.append("capital_requirement")
    if re.search(r"\bcapital\b", question, re.I) and re.search(
        r"\b(gap|shortfall|headroom|surplus|deficit)\b", question, re.I
    ):
        parts.append("capital_gap")
    if re.search(r"\b(deadlines?|due dates?|by when)\b", question, re.I):
        parts.append("deadline")
    return parts


def capital_records_needed(question):
    return bool("capital_gap" in requested_parts(question) and re.search(
        r"\b(our|my|we|us|this bank|this institution)\b", question, re.I
    ))


def coverage_gaps(question, claims, calculations, audited_parts=None):
    """An audited side fact cannot satisfy a requested amount, gap or deadline.

    The auditor's coverage flags are necessary when supplied, but never sufficient:
    a supported answer still needs a quantitative requirement, checked arithmetic,
    or an operative deadline. Missing metadata fails closed for capital questions.
    """
    texts = [item["text"] for item in claims]
    evidence = " ".join(texts)
    amount = r"(?:[₦$€£]|\b(?:NGN|USD|N))\s*\d|\d[\d,.]*\s*(?:billion|million|bn)\b"
    present = {
        "capital_requirement": any(
            re.search(r"\b(?:minimum|require\w*|threshold|shall|must|expected|reach|increase)\b", text, re.I)
            and re.search(amount, text, re.I)
            for text in texts
        ),
        "capital_gap": bool(calculations) and bool(re.search(
            r"\b(?:gap|shortfall|headroom|surplus|deficit|conditional|assuming|if)\b", evidence, re.I
        )),
        "deadline": any(
            re.search(r"\b(?:deadline|comply|meet|attain|achieve|by|not later|effective)\b", text, re.I)
            and re.search(r"\b(?:19|20)\d{2}\b", text)
            and not re.search(r"\b(?:revok\w*|revocation)\b", text, re.I)
            for text in texts
        ),
    }
    return [part for part in requested_parts(question)
            if not present[part] or (audited_parts is not None and part not in audited_parts)]


def join_parts(parts):
    labels = [PART_LABELS[part] for part in parts]
    return ", ".join(labels[:-1]) + " and " + labels[-1] if len(labels) > 1 else labels[0]
